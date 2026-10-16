"""Pure RouterOS change-plan builders.

The plans produced here are data only.  This module deliberately has no
RouterOS client and no apply function; callers must submit plans through the
existing Safe Change workflow before any command can run.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_VOUCHER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_RATE = re.compile(r"^[1-9][0-9]{0,8}[kMG]?$")


@dataclass(frozen=True)
class ChangePlan:
    action: str
    commands: list[str]
    expected_readback: dict[str, Any]
    risk: str = "high"
    execution_path: str = "safe_change_only"


@dataclass(frozen=True)
class ProtectionChange:
    guest_subnet: str
    guest_interface: str
    allow_dns: bool = True
    allow_dhcp: bool = True


@dataclass(frozen=True)
class FairShareChange:
    name: str
    target: str
    upload_limit: str
    download_limit: str
    disabled: bool = False


@dataclass(frozen=True)
class HotspotVoucherChange:
    voucher_id: str
    client_mac: str
    server: str
    minutes: int
    data_mb: int
    expires_at: datetime
    mac_auth_password: str = ""


def _quoted(value: str) -> str:
    if not isinstance(value, str) or any(ch in value for ch in "\r\n\x00"):
        raise ValueError("RouterOS text must be a single non-null line")
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return f'"{value}"'


def _name(value: str, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _network(value: str, label: str) -> str:
    try:
        network = ipaddress.ip_network(value, strict=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}") from error
    if network.version != 4 or network.is_multicast or network.is_unspecified:
        raise ValueError(f"invalid {label}")
    return str(network)


def _mac(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid client MAC")
    compact = re.sub(r"[:-]", "", value).upper()
    if not re.fullmatch(r"[0-9A-F]{12}", compact):
        raise ValueError("invalid client MAC")
    octets = [int(compact[i:i + 2], 16) for i in range(0, 12, 2)]
    if compact == "000000000000" or octets[0] & 1:
        raise ValueError("client MAC must be a non-zero unicast address")
    return ":".join(f"{part:02X}" for part in octets)


def build_protection_plan(change: ProtectionChange) -> ChangePlan:
    subnet = _network(change.guest_subnet, "guest subnet")
    interface = _name(change.guest_interface, "guest interface")
    if not isinstance(change.allow_dns, bool) or not isinstance(change.allow_dhcp, bool):
        raise ValueError("protection switches must be boolean")
    prefix = "mm-protection-" + interface
    rules: list[dict[str, str]] = []
    if change.allow_dhcp:
        rules.append({"chain": "input", "in-interface": interface, "protocol": "udp", "dst-port": "67", "action": "accept", "comment": prefix + "-dhcp"})
    if change.allow_dns:
        for protocol in ("udp", "tcp"):
            rules.append({"chain": "input", "in-interface": interface, "protocol": protocol, "dst-port": "53", "action": "accept", "comment": prefix + "-dns-" + protocol})
    rules.extend([
        {"chain": "input", "in-interface": interface, "src-address": subnet, "action": "drop", "comment": prefix + "-router"},
        {"chain": "forward", "in-interface": interface, "out-interface-list": "LAN", "action": "drop", "comment": prefix + "-lan"},
    ])
    commands = []
    for rule in rules:
        command = "/ip firewall filter add " + " ".join(f"{key}={_quoted(value)}" for key, value in rule.items())
        commands.append(command)
    return ChangePlan("protection", commands, {"rules": rules})


def build_fair_share_plan(change: FairShareChange) -> ChangePlan:
    name = _name(change.name, "queue name")
    target = _network(change.target, "queue target")
    if not _RATE.fullmatch(change.upload_limit or "") or not _RATE.fullmatch(change.download_limit or ""):
        raise ValueError("limits must be positive RouterOS rates such as 10M")
    if not isinstance(change.disabled, bool):
        raise ValueError("disabled must be boolean")
    owned = "mm-fair-share-" + name
    values = {
        "name": owned,
        "target": target,
        "max-limit": f"{change.upload_limit}/{change.download_limit}",
        "queue": "pcq-upload-default/pcq-download-default",
        "disabled": "yes" if change.disabled else "no",
        "comment": owned,
    }
    command = "/queue simple add " + " ".join(f"{key}={_quoted(value)}" for key, value in values.items())
    return ChangePlan("fair_share", [command], {"queue": values})


def build_hotspot_plan(change: HotspotVoucherChange, now: datetime | None = None) -> ChangePlan:
    if not isinstance(change.voucher_id, str) or not _VOUCHER_ID.fullmatch(change.voucher_id):
        raise ValueError("invalid voucher identity")
    mac = _mac(change.client_mac)
    server = _name(change.server, "HotSpot server")
    if not isinstance(change.minutes, int) or isinstance(change.minutes, bool) or not 1 <= change.minutes <= 525600:
        raise ValueError("voucher minutes must be 1-525600")
    if not isinstance(change.data_mb, int) or isinstance(change.data_mb, bool) or not 1 <= change.data_mb <= 1048576:
        raise ValueError("voucher data must be 1-1048576 MB")
    if not isinstance(change.expires_at, datetime) or change.expires_at.tzinfo is None:
        raise ValueError("voucher expiry must be timezone-aware")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("current time must be timezone-aware")
    current = current.astimezone(timezone.utc)
    expires = change.expires_at.astimezone(timezone.utc)
    if expires <= current or expires.timestamp() > current.timestamp() + change.minutes * 60 + 1:
        raise ValueError("invalid or expired guest voucher allowance")
    if not isinstance(change.mac_auth_password, str) or len(change.mac_auth_password) > 128:
        raise ValueError("invalid MAC authentication password")
    comment = "mega-magic:voucher:" + change.voucher_id
    scheduler = "mm-voucher-" + change.voucher_id
    selector = f"name={_quoted(mac)} comment={_quoted(comment)}"
    expiry_seconds = int(expires.timestamp())
    event = (
        f":if ([:timestamp] >= [:totime {_quoted(str(expiry_seconds) + 's')}]) do={{ "
        f":if ([:len [/ip hotspot user find {selector}]] > 0) do={{ "
        f"/ip hotspot user disable [find {selector}]; /ip hotspot active remove [find user={_quoted(mac)}] }}; "
        f"/system scheduler remove [find name={_quoted(scheduler)}] }}"
    )
    user = {
        "name": mac,
        "mac-address": mac,
        "server": server,
        "profile": "default",
        "comment": comment,
        "limit-uptime": f"{change.minutes * 60}s",
        "limit-bytes-total": str(change.data_mb * 1_000_000),
        "disabled": "yes",
    }
    add_fields = dict(user)
    add_fields["password"] = change.mac_auth_password
    add_user = "/ip hotspot user add " + " ".join(f"{key}={_quoted(value)}" for key, value in add_fields.items())
    add_guard = (
        "/system scheduler add "
        f"name={_quoted(scheduler)} start-time=startup interval=10s policy={_quoted('read,write')} on-event={_quoted(event)}"
    )
    enable = f"/ip hotspot user enable [find {selector}]"
    expected_user = dict(user)
    expected_user["disabled"] = "no"
    expected = {"user": expected_user, "guard": {"name": scheduler, "interval": "10s", "on-event": event, "disabled": "no"}}
    return ChangePlan("hotspot_voucher", [add_guard, add_user, enable], expected)


build_hotspot_voucher_plan = build_hotspot_plan


def build_change_plan(change: ProtectionChange | FairShareChange | HotspotVoucherChange, now: datetime | None = None) -> ChangePlan:
    if isinstance(change, ProtectionChange):
        return build_protection_plan(change)
    if isinstance(change, FairShareChange):
        return build_fair_share_plan(change)
    if isinstance(change, HotspotVoucherChange):
        return build_hotspot_plan(change, now=now)
    raise TypeError("unsupported typed change")


def _normalized(field: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if field == "disabled":
        return {"true": "yes", "false": "no"}.get(value.lower(), value.lower())
    if field == "interval" or field == "limit-uptime":
        match = re.fullmatch(r"([0-9]+)s", value)
        if match:
            return int(match.group(1))
    if field == "max-limit":
        def rate(part: str) -> int | None:
            match = re.fullmatch(r"([0-9]+)([kMG]?)", part)
            if not match:
                return None
            return int(match.group(1)) * {"": 1, "k": 1000, "M": 1_000_000, "G": 1_000_000_000}[match.group(2)]
        parts = value.split("/")
        converted = [rate(part) for part in parts]
        if len(converted) == 2 and None not in converted:
            return converted
    return value


def verify_readback(plan: ChangePlan, readback: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    if not isinstance(plan, ChangePlan):
        raise TypeError("plan must be a ChangePlan")
    if not isinstance(readback, Mapping):
        return False, {"$": {"expected": plan.expected_readback, "actual": readback}}
    diff: dict[str, Any] = {}

    def compare(expected: Any, actual: Any, path: str, field: str = "") -> None:
        if isinstance(expected, Mapping):
            if not isinstance(actual, Mapping):
                diff[path] = {"expected": expected, "actual": actual}
                return
            for key, value in expected.items():
                compare(value, actual.get(key), f"{path}.{key}" if path else str(key), str(key))
            return
        if isinstance(expected, list):
            if not isinstance(actual, list) or len(expected) != len(actual):
                diff[path] = {"expected": expected, "actual": actual}
                return
            for index, value in enumerate(expected):
                compare(value, actual[index], f"{path}[{index}]", field)
            return
        if _normalized(field, expected) != _normalized(field, actual):
            diff[path] = {"expected": expected, "actual": actual}

    compare(plan.expected_readback, readback, "")
    return not diff, diff
