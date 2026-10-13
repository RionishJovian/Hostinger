"""Safe Change: guest VLAN on a router Ethernet port for an external AP.

Creates (or adopts) a VLAN interface on a chosen ether/sfp port and joins it to
the guest HotSpot bridge so a tagged external AP feeds the existing HotSpot
guest network. When HotSpot still runs directly on wifi (lab), creates
`mm-guest-br`, moves the guest radio + IP/DHCP/HotSpot onto that bridge, then
adds the VLAN.

Refuses WAN/uplink (DHCP client / PPPoE), wifi1/Wi-Fi, Hub WireGuard, and the
HotSpot interface itself. Does not implement switch-port VLAN management (Q70).
No secrets belong in before/desired/diff/evidence.
"""
from __future__ import annotations

import hashlib
import json
import re

from fastapi import HTTPException

from .routeros_adapter import (
    GUEST_BRIDGE_NAME,
    RouterOSError,
    apply_guest_vlan_external_ap,
    guest_vlan_state,
    list_hotspot_servers,
    restore_guest_vlan_external_ap,
)

_IFACE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
_VLAN_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def require_flag(app):
    if not getattr(app.state, 'router_settings_changes_enabled', False):
        raise HTTPException(503, 'Guest Wi-Fi, addressing and VLAN Safe Changes are not enabled')


def _hotspot_interfaces(evidence_payload: dict, client) -> set[str]:
    names = set()
    inventory = (evidence_payload or {}).get('hotspot_portal_inventory') or {}
    for server in inventory.get('servers') or []:
        iface = server.get('interface')
        if isinstance(iface, str) and iface.strip():
            names.add(iface.strip())
    for server in list_hotspot_servers(client):
        iface = server.get('interface')
        if isinstance(iface, str) and iface.strip():
            names.add(iface.strip())
    return names


def _default_vlan_name(vlan_id: int) -> str:
    return f'mm-guest-vlan-{vlan_id}'


def _resolve_hotspot_interface(evidence_payload, client, hotspot_interface: str | None):
    allowed = _hotspot_interfaces(evidence_payload, client)
    if not allowed:
        raise RouterOSError('hotspot_missing', 'No guest/HotSpot interface is known from preflight or live inventory', 409)
    if hotspot_interface:
        if not _IFACE.fullmatch(hotspot_interface):
            raise RouterOSError('resource_invalid', 'HotSpot interface name is invalid', 422)
        if hotspot_interface not in allowed:
            raise RouterOSError(
                'not_guest_hotspot_interface',
                'Selected HotSpot interface is not the guest side shown by preflight or live HotSpot inventory',
                409,
            )
        return hotspot_interface
    if len(allowed) == 1:
        return next(iter(allowed))
    raise RouterOSError(
        'hotspot_ambiguous',
        'Multiple HotSpot interfaces exist; specify hotspot_interface explicitly',
        422,
    )


def build_desired(before: dict):
    """Desired end-state: VLAN present on ethernet and member of the guest bridge; HotSpot on that bridge."""
    guest_bridge = before['guest_bridge'] or GUEST_BRIDGE_NAME
    return {
        **before,
        'guest_bridge': guest_bridge,
        'vlan_exists': True,
        'vlan_interface_parent': before['ethernet_port'],
        'vlan_on_guest_bridge': True,
        'hotspot_iface_on_guest_bridge': True,
        'migration_needed': before.get('migration_needed', False),
        'guest_bridge_exists': True,
        'hotspot_server_interface': guest_bridge if before.get('migration_needed') or not before.get('hotspot_is_bridge') else before['hotspot_server_interface'],
        'address_interface': guest_bridge if before.get('migration_needed') and before.get('address_interface') == before.get('hotspot_interface_original') else before.get('address_interface'),
        'dhcp_interface': guest_bridge if before.get('migration_needed') and before.get('dhcp_interface') == before.get('hotspot_interface_original') else before.get('dhcp_interface'),
    }


def preview_state(
    client,
    evidence_payload,
    *,
    ethernet_port: str,
    vlan_id: int,
    vlan_name: str | None = None,
    hotspot_interface: str | None = None,
):
    if not isinstance(ethernet_port, str) or not _IFACE.fullmatch(ethernet_port):
        raise RouterOSError('ethernet_invalid', 'Ethernet port name is invalid', 422)
    try:
        vid = int(vlan_id)
    except (TypeError, ValueError) as error:
        raise RouterOSError('vlan_id_invalid', 'VLAN id must be an integer from 2 to 4094', 422) from error
    if not (2 <= vid <= 4094):
        raise RouterOSError('vlan_id_invalid', 'VLAN id must be an integer from 2 to 4094', 422)
    name = vlan_name or _default_vlan_name(vid)
    if not isinstance(name, str) or not _VLAN_NAME.fullmatch(name):
        raise RouterOSError('vlan_name_invalid', 'VLAN interface name is invalid', 422)
    if name.lower().startswith('wifi') or name.startswith('mm-975') or name == 'bridge':
        raise RouterOSError('vlan_name_invalid', 'VLAN name must not collide with Wi-Fi, Hub tunnel or LAN bridge names', 422)

    hs = _resolve_hotspot_interface(evidence_payload, client, hotspot_interface)
    before = guest_vlan_state(
        client, ethernet_port=ethernet_port, vlan_id=vid, vlan_name=name, hotspot_interface=hs,
    )
    desired = build_desired(before)
    # Drop ephemeral apply flags from persisted desired.
    desired.pop('_created', None)
    diff = {
        'ethernet_port': ethernet_port,
        'vlan_id': {'before': before['vlan_id'] if before['vlan_exists'] else None, 'after': vid},
        'vlan_name': {'before': before['vlan_name'] if before['vlan_exists'] else None, 'after': name},
        'vlan_exists': {'before': before['vlan_exists'], 'after': True},
        'guest_bridge': {'before': before['guest_bridge'] if before['guest_bridge_exists'] else None, 'after': desired['guest_bridge']},
        'vlan_on_guest_bridge': {'before': before['vlan_on_guest_bridge'], 'after': True},
        'hotspot_server_interface': {
            'before': before.get('hotspot_server_interface'),
            'after': desired.get('hotspot_server_interface'),
        },
        'migration_needed': before.get('migration_needed', False),
        'objects': ['interface/vlan', 'interface/bridge', 'interface/bridge/port', 'ip/address', 'ip/dhcp-server', 'ip/hotspot'],
        'impact': (
            'Tagged frames from an external AP on the chosen Ethernet port join the guest HotSpot bridge. '
            'If HotSpot still runs on the guest radio alone, MikroMagic creates mm-guest-br and moves '
            'guest IP/DHCP/HotSpot onto that bridge. WAN/uplink, wifi1, Hub WireGuard and the LAN management bridge stay out of scope. '
            'Switch-port VLAN management (Q70) is not performed.'
        ),
        'fingerprint': fingerprint({'before': verify_shape(before), 'desired': verify_shape(desired)}),
    }
    return before, desired, diff


def read_actual(client, expected):
    return guest_vlan_state(
        client,
        ethernet_port=expected['ethernet_port'],
        vlan_id=expected['vlan_id'],
        vlan_name=expected['vlan_name'],
        hotspot_interface=expected['hotspot_interface_original'],
    )


def verify_shape(state: dict) -> dict:
    """Comparable fields for before/desired verification (no secrets, no ephemeral ids-only noise)."""
    return {
        'ethernet_port': state.get('ethernet_port'),
        'vlan_id': state.get('vlan_id'),
        'vlan_name': state.get('vlan_name'),
        'vlan_exists': bool(state.get('vlan_exists')),
        'vlan_interface_parent': state.get('vlan_interface_parent') or state.get('ethernet_port'),
        'guest_bridge': state.get('guest_bridge'),
        'vlan_on_guest_bridge': bool(state.get('vlan_on_guest_bridge')),
        'hotspot_iface_on_guest_bridge': bool(state.get('hotspot_iface_on_guest_bridge')),
        'hotspot_server_interface': state.get('hotspot_server_interface'),
    }


def apply_change(client, before, desired):
    live = apply_guest_vlan_external_ap(client, before, desired)
    # Re-read canonical state; keep _created for rollback.
    actual = guest_vlan_state(
        client,
        ethernet_port=desired['ethernet_port'],
        vlan_id=desired['vlan_id'],
        vlan_name=desired['vlan_name'],
        hotspot_interface=desired['hotspot_interface_original'],
    )
    actual['_created'] = live.get('_created') or {}
    actual['ids'] = live.get('ids') or actual.get('ids')
    return actual


def rollback_change(client, before, desired=None):
    restore_guest_vlan_external_ap(client, before, desired)
    return guest_vlan_state(
        client,
        ethernet_port=before['ethernet_port'],
        vlan_id=before['vlan_id'],
        vlan_name=before['vlan_name'],
        hotspot_interface=before['hotspot_interface_original'],
    )
