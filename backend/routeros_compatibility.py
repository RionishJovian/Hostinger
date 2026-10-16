"""Evidence-based RouterOS compatibility classification for Magic Connect.

This is a preflight decision aid, not a certification of a model or a router
write. Unknown values fail closed to manual review.
"""
import re


KNOWN_ROUTEROS7_ARCHITECTURES = frozenset({
    "arm", "arm64", "mipsbe", "mmips", "smips", "tile", "ppc", "x86", "chr",
})


def _version(value):
    if not isinstance(value, str):
        return None
    match = re.match(r"^\s*(\d+)\.(\d+)(?:\.(\d+))?(.*)$", value, re.I)
    if not match:
        return None
    suffix = match.group(4).strip().lower()
    if any(flag in suffix for flag in ("beta", "rc", "testing", "development")):
        return {"parsed": ".".join(match.group(i) for i in (1, 2, 3) if match.group(i)), "stable": False}
    return {"parsed": ".".join(match.group(i) for i in (1, 2, 3) if match.group(i)), "stable": True}


def classify_routeros_compatibility(identity, capabilities, transport, read_access_verified=True):
    """Classify whether post-connection evidence supports later Safe Change review.

    It never means a peer was installed or a connection works. RouterOS 7 is
    required by frozen v1; the actual WireGuard REST resource and a verified
    HTTPS read are checked on-device because minor releases and architectures
    can differ. Architecture is recorded, not used as a blanket performance
    guarantee.
    """
    identity = identity if isinstance(identity, dict) else {}
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    transport = transport if isinstance(transport, dict) else {}
    reasons = []
    version = identity.get("version")
    parsed = _version(version)
    architecture = identity.get("architecture-name")
    architecture = architecture.strip().lower() if isinstance(architecture, str) else ""

    if not parsed:
        reasons.append("RouterOS version is missing or could not be parsed from live discovery.")
    elif not parsed["stable"]:
        reasons.append("Prerelease/testing RouterOS builds require explicit compatibility review.")
    elif int(parsed["parsed"].split(".", 1)[0]) < 7:
        reasons.append("Magic Connect requires RouterOS v7 or later for WireGuard.")

    if not architecture:
        reasons.append("CPU architecture was not reported; model compatibility cannot be assessed.")
    elif architecture == "mipsle":
        reasons.append("This legacy architecture is not compatible with RouterOS v7; upgrade eligibility must be checked with MikroTik.")
    elif architecture not in KNOWN_ROUTEROS7_ARCHITECTURES:
        reasons.append("Unrecognized CPU architecture requires compatibility review.")

    if capabilities.get("wireguard") is not True:
        reasons.append("The live WireGuard interface resource was not detected with the monitoring identity.")
    if transport.get("scheme") != "https" or transport.get("tls_verified") is not True:
        reasons.append("A certificate-verified HTTPS management read is required.")
    if read_access_verified is not True:
        reasons.append("The dedicated monitoring identity has not completed an authenticated read.")

    hard_unsupported = bool(parsed and parsed["stable"] and int(parsed["parsed"].split(".", 1)[0]) < 7) or architecture == "mipsle"
    complete = not reasons
    status = "compatible_for_safe_change" if complete else ("unsupported" if hard_unsupported else "needs_review")
    return {
        "status": status,
        "routeros_version": version,
        "routeros_version_parsed": parsed["parsed"] if parsed else None,
        "routeros_channel_eligible": bool(parsed and parsed["stable"] and int(parsed["parsed"].split(".", 1)[0]) >= 7),
        "wireguard_detected": capabilities.get("wireguard") is True,
        "architecture": architecture or None,
        "architecture_recognized_for_routeros7": architecture in KNOWN_ROUTEROS7_ARCHITECTURES,
        "management_permissions": {
            "monitoring_read": "verified" if read_access_verified else "unverified",
            "safe_change_write": "not_tested",
            "note": "No write permission is inferred or tested during preflight.",
        },
        "reasons": reasons,
        "router_configuration_changed": False,
        "connection_verified": False,
    }
