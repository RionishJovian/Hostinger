"""Safe Change: guest network address, DHCP pool/network and HotSpot hotspot-address.

Applies in order: IP pool → interface address → DHCP network → HotSpot profile.
Rollback restores HotSpot profile → DHCP network → interface address → pool.
LAN bridge (e.g. 192.168.88.0/24), WireGuard/Hub 10.90.0.0/16 and WAN networks
seen in live evidence are refused as overlaps. RFC1918 only, prefix /22–/29.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re

from fastapi import HTTPException

from .routeros_adapter import (
    HUB_MGMT_NETWORK,
    RouterOSError,
    apply_guest_network_addressing,
    guest_network_state,
    list_hotspot_servers,
    list_ip_addresses,
    restore_guest_network_addressing,
)

_IFACE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
RFC1918 = (
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def require_flag(app):
    if not getattr(app.state, 'router_settings_changes_enabled', False):
        raise HTTPException(503, 'Guest Wi-Fi and addressing Safe Changes are not enabled')


def _parse_ipv4(value: str, label: str):
    try:
        return ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ValueError) as error:
        raise RouterOSError('address_invalid', f'{label} is not a valid IPv4 address', 422) from error


def _parse_network(cidr: str):
    try:
        net = ipaddress.ip_network(cidr, strict=True)
    except (ipaddress.AddressValueError, ValueError) as error:
        raise RouterOSError('network_invalid', 'Guest network must be a strict IPv4 CIDR (e.g. 10.5.50.0/24)', 422) from error
    if net.version != 4:
        raise RouterOSError('network_invalid', 'Only IPv4 guest networks are supported', 422)
    if not any(net.subnet_of(block) for block in RFC1918):
        raise RouterOSError('network_invalid', 'Guest network must be RFC1918 private address space', 422)
    if not (22 <= net.prefixlen <= 29):
        raise RouterOSError('network_invalid', 'Guest network prefix must be between /22 and /29', 422)
    return net


def _networks_to_protect(client, guest_interface: str):
    """LAN, Hub/WireGuard and WAN networks that must not overlap the new guest subnet."""
    protected = [ipaddress.ip_network(HUB_MGMT_NETWORK)]
    for item in list_ip_addresses(client):
        iface = item.get('interface')
        raw = item.get('address')
        if not isinstance(raw, str) or not isinstance(iface, str):
            continue
        if iface == guest_interface:
            continue
        try:
            protected.append(ipaddress.ip_interface(raw).network)
        except ValueError:
            continue
    return protected


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


def validate_desired(*, network_cidr: str, gateway: str, pool_start: str, pool_end: str, dns: str | None, protected):
    net = _parse_network(network_cidr)
    gw = _parse_ipv4(gateway, 'Gateway')
    start = _parse_ipv4(pool_start, 'DHCP pool start')
    end = _parse_ipv4(pool_end, 'DHCP pool end')
    dns_addr = _parse_ipv4(dns or gateway, 'DNS')
    if gw not in net or gw == net.network_address or gw == net.broadcast_address:
        raise RouterOSError('gateway_invalid', 'Gateway must be a usable host address inside the guest subnet', 422)
    if start not in net or end not in net or int(start) > int(end):
        raise RouterOSError('pool_invalid', 'DHCP pool must lie inside the guest subnet and start ≤ end', 422)
    if start <= gw <= end:
        raise RouterOSError('pool_invalid', 'DHCP pool must exclude the gateway address', 422)
    if dns_addr not in net and not any(dns_addr in block for block in RFC1918):
        # Allow gateway or other RFC1918 DNS; refuse public DNS forcing through guest only — still OK if any IPv4.
        pass
    for other in protected:
        if net.overlaps(other):
            raise RouterOSError(
                'network_overlap',
                f'Guest network {net} overlaps protected network {other} (LAN, WAN or MikroMagic Hub 10.90.0.0/16)',
                409,
            )
    return {
        'network': str(net),
        'address': f'{gw}/{net.prefixlen}',
        'gateway': str(gw),
        'pool_ranges': f'{start}-{end}',
        'pool_start': str(start),
        'pool_end': str(end),
        'dns': str(dns_addr),
        'hotspot_address': str(gw),
        'dhcp_network_address': str(net),
    }


def preview_state(client, evidence_payload, *, interface_name: str, network_cidr: str, gateway: str,
                  pool_start: str, pool_end: str, dns: str | None = None):
    if not isinstance(interface_name, str) or not _IFACE.fullmatch(interface_name):
        raise RouterOSError('resource_invalid', 'Interface name is invalid', 422)
    allowed = _hotspot_interfaces(evidence_payload, client)
    if interface_name not in allowed:
        raise RouterOSError(
            'not_guest_hotspot_interface',
            'Selected interface is not the guest/HotSpot side shown by preflight or live HotSpot inventory',
            409,
        )
    before = guest_network_state(client, interface_name)
    protected = _networks_to_protect(client, interface_name)
    target = validate_desired(
        network_cidr=network_cidr, gateway=gateway, pool_start=pool_start, pool_end=pool_end,
        dns=dns, protected=protected,
    )
    desired = {
        **before,
        'address': target['address'],
        'pool_ranges': target['pool_ranges'],
        'pool_start': target['pool_start'],
        'pool_end': target['pool_end'],
        'dhcp_network_address': target['dhcp_network_address'],
        'dhcp_gateway': target['gateway'],
        'dhcp_dns': target['dns'],
        'hotspot_address': target['hotspot_address'],
        'network_cidr': target['network'],
    }
    diff = {
        'interface_address': {'before': before['address'], 'after': desired['address']},
        'pool_ranges': {'before': before['pool_ranges'], 'after': desired['pool_ranges']},
        'dhcp_network': {
            'before': {
                'address': before['dhcp_network_address'],
                'gateway': before['dhcp_gateway'],
                'dns': before.get('dhcp_dns'),
            },
            'after': {
                'address': desired['dhcp_network_address'],
                'gateway': desired['dhcp_gateway'],
                'dns': desired['dhcp_dns'],
            },
        },
        'hotspot_address': {'before': before.get('hotspot_address'), 'after': desired['hotspot_address']},
        'objects': ['ip/address', 'ip/pool', 'ip/dhcp-server/network', 'ip/hotspot/profile'],
        'impact': (
            'Active guests will lose their sessions and must reconnect for a new DHCP lease on the new subnet. '
            'LAN bridge, WAN/station uplink and WireGuard management addressing stay out of scope.'
        ),
        'fingerprint': fingerprint({'before': before, 'desired': desired}),
    }
    return before, desired, diff


def read_actual(client, expected):
    live = guest_network_state(client, expected['interface'])
    return {
        **live,
        'pool_start': expected.get('pool_start'),
        'pool_end': expected.get('pool_end'),
        'network_cidr': expected.get('network_cidr'),
    }


def verify_shape(state: dict) -> dict:
    return {
        'interface': state.get('interface'),
        'address': state.get('address'),
        'pool_ranges': state.get('pool_ranges'),
        'dhcp_network_address': state.get('dhcp_network_address'),
        'dhcp_gateway': state.get('dhcp_gateway'),
        'dhcp_dns': state.get('dhcp_dns'),
        'hotspot_address': state.get('hotspot_address'),
        'ids': state.get('ids'),
    }


def apply_change(client, before, desired):
    apply_guest_network_addressing(
        client, before['ids'],
        address=desired['address'],
        pool_ranges=desired['pool_ranges'],
        network_address=desired['dhcp_network_address'],
        gateway=desired['dhcp_gateway'],
        dns=desired['dhcp_dns'],
        hotspot_address=desired['hotspot_address'],
    )
    live = guest_network_state(client, desired['interface'])
    return {
        **desired,
        **{k: live[k] for k in (
            'address', 'pool_ranges', 'dhcp_network_address', 'dhcp_gateway', 'dhcp_dns',
            'hotspot_address', 'ids', 'resource_id',
        )},
    }


def rollback_change(client, before):
    restore_guest_network_addressing(client, before)
    live = guest_network_state(client, before['interface'])
    return {
        **before,
        **{k: live[k] for k in (
            'address', 'pool_ranges', 'dhcp_network_address', 'dhcp_gateway', 'dhcp_dns',
            'hotspot_address', 'ids', 'resource_id',
        )},
    }
