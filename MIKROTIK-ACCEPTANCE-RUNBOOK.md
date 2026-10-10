# MikroMagic MikroTik Acceptance Runbook

This runbook is for the first real integration session. A feature is accepted only when the result is observed on the real test router and recorded with timestamp, RouterOS version, device identity, and operator.

## Required test environment

- Disposable MikroTik RouterBOARD with console or WinBox recovery access
- Exact model, architecture, RouterOS version and license level
- One Magic Hub VPS with WireGuard endpoint and peer key management
- One site LAN with a managed switch and at least one AP
- One WAN path representing the SME deployment; Starlink limits recorded separately from router counters
- Two guest test devices, one trusted operator device, and one device for bypass/IPv6 checks
- Test portal hostname/TLS origin and a disposable test business
- Backup destination that can be restored independently

## Gate A — enrollment and WireGuard

1. Register the site and RouterBOARD with owner-reported metadata.
2. Generate the management-only plan and confirm guest traffic is not routed through the Hub.
3. Capture the pre-change RouterOS export and checksum.
4. Apply the minimum WireGuard peer/interface configuration through the approved transport.
5. Verify the live handshake timestamp, peer public key, allowed address, route, firewall isolation and management reachability.
6. Confirm that a Hub outage does not interrupt an already active local HotSpot policy.
7. Record evidence in the router and application audit logs.

Pass condition: the app reports connected only after live handshake and reachability evidence is received.

## Gate B — capability discovery and safe apply

1. Discover RouterOS version, architecture, HotSpot support, interface names, bridge/VLAN layout, IPv4/IPv6 behavior, User Manager/RADIUS availability, storage and license.
2. Compare discovered capabilities with the requested portal policy.
3. Reject unsupported or conflicting settings before apply.
4. Show a human-readable diff and expected impact.
5. Take a recoverable backup.
6. Apply a small reversible change, such as a test address-list or profile attribute.
7. Verify observed state after apply.
8. Roll back and verify the original state.

Pass condition: no successful result is reported without post-change observation.

## Gate C — HotSpot and walled garden

1. Publish the site portal with only required pre-login destinations.
2. Verify redirect from an unauthenticated client.
3. Verify catalogue, payment instructions and voucher entry are reachable.
4. Verify unauthorized internet and direct media paths are blocked.
5. Verify IPv4 and IPv6 behavior separately.
6. Verify guest traffic remains on the site WAN and does not use the management tunnel.
7. Verify trusted and blocked device behavior.

## Gate D — voucher and quota enforcement

Create separate test profiles for:

- time-only access
- data-only access
- combined time and data access

For each profile:

1. Issue a cryptographically random voucher.
2. Redeem it once and confirm duplicate redemption is rejected.
3. Verify the configured speed and concurrent-session limit.
4. Consume time and/or bytes using controlled test traffic.
5. Verify access stops at the first configured limit.
6. Reconnect the device and confirm counters do not reset.
7. Reboot the router and confirm valid counters survive.
8. Disable or revoke the voucher and verify the configured grace behavior.
9. Compare RouterOS/AAA accounting with MikroMagic usage records.

Pass condition: all quota decisions are enforced locally and reconciled without double consumption.

## Gate E — failure and rollback

Test each failure independently:

- cloud API unavailable
- WireGuard tunnel unavailable
- WAN unavailable
- partial device apply
- router reboot during apply
- invalid or unsupported RouterOS capability
- stale configuration revision
- duplicate usage event
- clock skew
- failed backup or restore

Each failure must produce a visible pending/error state, preserve existing valid local policy, and provide an operator recovery action.

## Evidence required before marking complete

- Router model, serial or MAC, RouterOS version and license
- Before/after exports and checksums
- WireGuard handshake evidence
- Capability discovery response
- Apply diff, operator approval and post-apply observation
- Rollback result
- HotSpot redirect and walled-garden captures
- Voucher/profile IDs and accounting records
- Quota exhaustion and reconnect results
- Failure test results
- Application audit events and timestamps

No live integration row in `STATUS.md` should move to verified until this evidence exists.
