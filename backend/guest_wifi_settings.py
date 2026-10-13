"""Safe Change: guest Wi-Fi SSID and security (RouterOS 7 /interface/wifi).

Design — configuration / security profile handling
-------------------------------------------------
RouterOS 7 wifi interfaces may carry SSID/security inline
(`configuration.ssid`, `security.authentication-types`, `security.passphrase`)
or reference named `/interface/wifi/configuration` and `/interface/wifi/security`
profiles.

Chosen behaviour:
- Inline bindings: PATCH the interface itself.
- Named profiles used solely by the selected interface: PATCH that profile.
- Named profiles shared with any other wifi interface: refuse (no silent
  cross-SSID impact).
- Never create, rename, or delete profiles as a side effect.
- Passphrases are never stored in plaintext in before/desired/actual/diff/
  evidence/audit. When a WPA passphrase is required for apply, it is held only
  as Fernet ciphertext (derived from MIKROMAGIC_BACKUP_KEY) inside desired and
  redacted from API responses.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from fastapi import HTTPException

from .backup_key import derived_fernet
from .routeros_adapter import (
    RouterOSError,
    apply_wifi_settings,
    list_bridge_ports,
    list_hotspot_servers,
    list_wifi_interfaces,
    wifi_interface_state,
)
from .schemas import printed_ssid

PASSPHRASE_INFO = b'mikromagic-guest-wifi-passphrase-v1'
_STATION = re.compile(r'station', re.I)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _cipher():
    raw = os.environ.get('MIKROMAGIC_BACKUP_KEY')
    cipher = derived_fernet(raw, PASSPHRASE_INFO) if raw else None
    if cipher is None:
        raise RouterOSError('backup_key_missing', 'Encrypted backup key is not configured', 500)
    return cipher


def encrypt_passphrase(passphrase: str) -> str:
    return _cipher().encrypt(passphrase.encode('utf-8')).decode('ascii')


def decrypt_passphrase(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode('ascii')).decode('utf-8')
    except Exception as error:
        raise RouterOSError('passphrase_unavailable', 'Stored Wi-Fi passphrase could not be unlocked', 409) from error


def redact_state(value):
    """Strip ciphertext and any accidental plaintext passphrase from API/audit shapes."""
    if not isinstance(value, dict):
        return value
    out = {k: v for k, v in value.items() if k not in ('passphrase', 'passphrase_ciphertext', 'security.passphrase')}
    return out


def redact_diff(diff):
    if not isinstance(diff, dict):
        return diff
    out = dict(diff)
    if 'passphrase' in out:
        out['passphrase'] = {'before': 'set' if out['passphrase'].get('before') else 'unset',
                             'after': out['passphrase'].get('after', 'unchanged')}
    return out


def require_flag(app):
    if not getattr(app.state, 'router_settings_changes_enabled', False):
        raise HTTPException(503, 'Guest Wi-Fi, addressing and VLAN Safe Changes are not enabled')


def _hotspot_interfaces_from_evidence(evidence_payload: dict) -> set[str]:
    inventory = (evidence_payload or {}).get('hotspot_portal_inventory') or {}
    names = set()
    for server in inventory.get('servers') or []:
        iface = server.get('interface')
        if isinstance(iface, str) and iface.strip():
            names.add(iface.strip())
    return names


def _assert_guest_wifi_allowed(client, interface_name: str, evidence_payload: dict):
    hotspot_ifaces = _hotspot_interfaces_from_evidence(evidence_payload)
    live_hotspot = {s.get('interface') for s in list_hotspot_servers(client) if isinstance(s.get('interface'), str)}
    allowed = hotspot_ifaces | live_hotspot
    if interface_name not in allowed:
        raise RouterOSError(
            'not_guest_hotspot_interface',
            'Selected interface is not the guest/HotSpot side shown by preflight or live HotSpot inventory',
            409,
        )
    interfaces = list_wifi_interfaces(client)
    iface = next((i for i in interfaces if i.get('name') == interface_name), None)
    if not iface:
        raise RouterOSError('wifi_missing', 'The selected Wi-Fi interface is not present', 409)
    mode = str(iface.get('configuration.mode') or iface.get('mode') or '').lower()
    if _STATION.search(mode) or 'station' in mode:
        raise RouterOSError('wan_station_forbidden', 'Station/WAN Wi-Fi interfaces must never be changed', 409)
    # Refuse non-HotSpot interfaces that sit in a LAN bridge.
    bridge_ports = list_bridge_ports(client)
    in_bridge = any(p.get('interface') == interface_name for p in bridge_ports)
    if in_bridge and interface_name not in allowed:
        raise RouterOSError('lan_bridge_forbidden', 'Interfaces in the LAN bridge cannot be changed unless they are the HotSpot interface', 409)
    return iface


def build_desired(before: dict, *, ssid: str, security_mode: str, passphrase: str | None):
    ssid = printed_ssid(ssid)
    if not ssid:
        raise RouterOSError('ssid_invalid', 'SSID is required', 422)
    if security_mode not in ('open', 'wpa2_wpa3_psk'):
        raise RouterOSError('security_invalid', 'Security must be open or WPA2/WPA3-PSK', 422)
    security_unchanged = security_mode == before.get('security_mode') and passphrase is None
    desired = {
        **{k: v for k, v in before.items() if k != '_passphrase_secret'},
        'ssid': ssid,
        'security_mode': security_mode,
        'authentication_types': '' if security_mode == 'open' else (
            before.get('authentication_types') or 'wpa2-psk,wpa3-psk' if security_unchanged else 'wpa2-psk,wpa3-psk'
        ),
        'passphrase_set': False if security_mode == 'open' else True,
        'touch_security': not security_unchanged,
    }
    if security_mode == 'open':
        desired.pop('passphrase_ciphertext', None)
        desired['authentication_types'] = ''
    elif passphrase is not None:
        if not isinstance(passphrase, str) or not (8 <= len(passphrase) <= 63):
            raise RouterOSError('passphrase_invalid', 'WPA passphrase must be 8–63 characters', 422)
        if any(ord(c) < 32 or ord(c) == 127 for c in passphrase):
            raise RouterOSError('passphrase_invalid', 'WPA passphrase cannot contain control characters', 422)
        desired['passphrase_ciphertext'] = encrypt_passphrase(passphrase)
        desired['authentication_types'] = 'wpa2-psk,wpa3-psk'
    elif security_mode == 'wpa2_wpa3_psk' and before.get('security_mode') != 'wpa2_wpa3_psk':
        raise RouterOSError('passphrase_invalid', 'WPA passphrase is required when enabling Wi-Fi security', 422)
    return desired


def _persistable_before(before_live: dict) -> dict:
    """Drop ephemeral secrets; keep encrypted passphrase for deterministic rollback when available."""
    secret = before_live.pop('_passphrase_secret', None)
    before = redact_state(before_live)
    if secret and before.get('security_mode') != 'open':
        before['passphrase_ciphertext'] = encrypt_passphrase(secret)
        before['passphrase_set'] = True
    elif before.get('security_mode') != 'open' and before.get('passphrase_set') and not before.get('passphrase_ciphertext'):
        # RouterOS hid the old passphrase — WPA→open / passphrase changes cannot auto-roll back.
        before['rollback_passphrase_available'] = False
    else:
        before['rollback_passphrase_available'] = True
    if 'rollback_passphrase_available' not in before:
        before['rollback_passphrase_available'] = bool(before.get('passphrase_ciphertext') or before.get('security_mode') == 'open')
    return before


def preview_state(client, evidence_payload, *, interface_name: str, ssid: str, security_mode: str, passphrase: str | None):
    _assert_guest_wifi_allowed(client, interface_name, evidence_payload)
    before_live = wifi_interface_state(client, interface_name)
    if before_live.get('configuration_shared') or before_live.get('security_shared'):
        before_live.pop('_passphrase_secret', None)
        raise RouterOSError(
            'shared_wifi_profile',
            'The Wi-Fi configuration or security profile is shared with another interface; refuse or change only a sole-use profile',
            409,
        )
    before = _persistable_before(before_live)
    desired = build_desired(before, ssid=ssid, security_mode=security_mode, passphrase=passphrase)
    # Security changes that need the old passphrase for rollback must have it encrypted in before.
    if desired.get('touch_security') and before.get('security_mode') != 'open' and not before.get('passphrase_ciphertext'):
        raise RouterOSError(
            'rollback_passphrase_unavailable',
            'RouterOS did not return the current WPA passphrase; refusing a security change that cannot be rolled back automatically. SSID-only changes are still allowed.',
            409,
        )
    if security_mode == 'open':
        passphrase_after = 'unset'
    elif desired.get('touch_security') and passphrase is not None:
        passphrase_after = 'changed' if before.get('passphrase_set') else 'set'
    else:
        passphrase_after = 'unchanged'
    diff = {
        'ssid': {'before': before['ssid'], 'after': desired['ssid']},
        'security_mode': {'before': before['security_mode'], 'after': desired['security_mode']},
        'passphrase': {
            'before': 'set' if before.get('passphrase_set') else 'unset',
            'after': passphrase_after,
        },
        'configuration_binding': before['configuration_binding'],
        'security_binding': before['security_binding'],
        'impact': (
            'Connected guests will be disconnected and must rejoin the Wi-Fi with the new name/security. '
            'WAN/station radio, LAN bridge, WireGuard management and HotSpot server objects stay out of scope.'
        ),
        'passphrase_changed': security_mode == 'wpa2_wpa3_psk',
        'fingerprint': fingerprint({'before': redact_state(before), 'desired': redact_state(desired)}),
    }
    return before, desired, diff


def read_actual(client, expected):
    live = wifi_interface_state(client, expected['interface'])
    # Fingerprint-comparable shape: ignore binding metadata drift that does not affect guest settings.
    return {
        **{k: live[k] for k in (
            'resource_id', 'interface', 'ssid', 'mode', 'security_mode', 'authentication_types',
            'passphrase_set', 'configuration_binding', 'configuration_name', 'configuration_shared',
            'security_binding', 'security_name', 'security_shared', 'disabled',
        )},
    }


def comparable(state: dict) -> dict:
    """Fields that must match for before/desired verification (no secrets)."""
    return redact_state({
        k: state.get(k) for k in (
            'resource_id', 'interface', 'ssid', 'security_mode', 'authentication_types',
            'passphrase_set', 'configuration_binding', 'configuration_name',
            'security_binding', 'security_name',
        )
    })


def apply_change(client, before, desired):
    passphrase = None
    touch_security = bool(desired.get('touch_security', True))
    if touch_security and desired['security_mode'] == 'wpa2_wpa3_psk':
        token = desired.get('passphrase_ciphertext')
        if not token:
            raise RouterOSError('passphrase_unavailable', 'WPA passphrase is missing from the preview', 409)
        passphrase = decrypt_passphrase(token)
    try:
        live = apply_wifi_settings(
            client, before,
            ssid=desired['ssid'],
            security_mode=desired['security_mode'],
            passphrase=passphrase,
            touch_security=touch_security,
        )
    finally:
        passphrase = None
    # Drop ephemeral secret from read-back before persistence.
    live.pop('_passphrase_secret', None)
    return {**desired, **{k: live[k] for k in (
        'resource_id', 'ssid', 'security_mode', 'authentication_types', 'passphrase_set',
        'configuration_binding', 'security_binding', 'disabled', 'mode',
    ) if k in live}}


def rollback_change(client, before):
    before = dict(before)
    before.pop('_passphrase_secret', None)
    if before['security_mode'] == 'open':
        live = apply_wifi_settings(
            client, before, ssid=before['ssid'], security_mode='open', passphrase=None, touch_security=True,
        )
        live.pop('_passphrase_secret', None)
        return {**before, **{k: live[k] for k in ('ssid', 'security_mode', 'authentication_types', 'passphrase_set') if k in live}}
    # Prefer full restore when we have the old passphrase; otherwise SSID-only rollback.
    token = before.get('passphrase_ciphertext')
    if token:
        passphrase = decrypt_passphrase(token)
        try:
            live = apply_wifi_settings(
                client, before, ssid=before['ssid'], security_mode='wpa2_wpa3_psk',
                passphrase=passphrase, touch_security=True,
            )
        finally:
            passphrase = None
    else:
        live = apply_wifi_settings(
            client, before, ssid=before['ssid'], security_mode=before['security_mode'],
            passphrase=None, touch_security=False,
        )
    live.pop('_passphrase_secret', None)
    return {**before, **{k: live[k] for k in ('ssid', 'security_mode', 'authentication_types', 'passphrase_set') if k in live}}
