# Magic Connect first physical session — preparation only

Status: **READY for owner-led, read-only RouterOS inspection after separate approval. NOT READY for bootstrap or a configuration-changing connection test.** No physical router has been inspected in this task.

This is the first-session checklist for one non-production router. It does not certify other models or RouterOS versions. The frozen Notion tracker remains authoritative; the first device is one compatibility sample only.

## Existing software and isolated Hub boundary

- Existing software provides tenant/site-scoped pairing, 10-minute single-claim codes, owner approval/denial/cancellation, a compatibility matrix, proposal-only router plans, and separate fresh-handshake plus authenticated identity-bound read gates before `Connected`.
- The proposal snapshot lists intended changes/exclusions but is not a RouterOS script. Dispatch remains `not_implemented`; host peer operations remain gated and off by default.
- `WireGuardHubAdapter` operates on a preconfigured local WireGuard interface through local `wg`; it does not create a Hub interface/key, routes, firewall, or standalone service. It must never target production or a personal VPN interface.
- Docker CLI/Compose are installed, but the Docker daemon is unavailable in this Mac session. No isolated Hub container, interface, keys, peer, secret, or service has been created. The current adapter is not wired to a separate Hub-container network namespace. A runtime Hub needs a reviewed development-only adapter/service arrangement, separate test DB, test-only keys, private network and rendered-config validation. Starting it is a later, separately approved action after read-only inspection.

## Stage 1 — read-only router inspection

Do not power on or inspect the router until the owner explicitly approves the physical read-only session. When approved:

1. Preserve current cabling/configuration. Do not reset the router, change passwords, enable services, import scripts, install packages, or alter firewall/WAN/LAN/DHCP/DNS/HotSpot/VPN settings.
2. Connect the Mac to the existing trusted management LAN or Wi-Fi. If using Ethernet, use a known LAN port, not WAN/uplink. Keep the Mac's current network configuration; do not set a static address unless separately discussed.
3. If WinBox is already available, use **Neighbors** on the directly connected LAN to identify the device, then connect using the observed MAC or already-known management IP. Use the existing authorized RouterOS login locally. Never send its password to MikroMagic or chat. If no trusted local access method is available, stop; do not alter access settings.
4. View only: **System → Resources** (RouterOS version/architecture); **System → RouterBOARD** (board/model); **System → Packages**; **Interfaces** (including WireGuard availability); **IP → Addresses**, **IP → Routes**, and **IP → Firewall → Filter Rules**; existing VPN/interface names. Do not edit, enable, disable, add, remove or reorder rules.
5. Record only exact model/board, RouterOS version, architecture, WireGuard availability, existing VPN names/count, relevant address prefixes, route destinations, and whether management services appear source-restricted. Do not send a full export or unredacted screenshots. Redact serial/MAC identifiers, public IPs, Wi-Fi credentials, names, and unrelated config. Never disclose private keys or reusable credentials.
6. Stop after collecting read-only facts. Do not click Apply/Save/Reset or run a supplied script. No MikroMagic identity, Hub peer, tunnel, route, firewall rule or credential is created during this stage.

Result: a capability assessment labelled **observed on one device**, with unknowns left unknown. Model name alone is not compatibility proof. RouterOS v7+, architecture and visible WireGuard availability are initial evidence only; authenticated capabilities can be checked only after a separately approved connection exists.

## Gates before any bootstrap authorization

1. **Pairing:** Verify tenant/site/device-attempt binding, logged-in Owner approval, comparison phrase, expiry, single-use/replay denial, cancellation and secret-free audit. The 10-minute QR/code is owner-to-technician handoff only, not router authorization; a separate short-lived single-use device-enrollment capability is still a design gap.
2. **Bootstrap:** Review an exact before/after plan. Router generates its WireGuard private key locally; only its public key is submitted over HTTPS with certificate validation. Detect interface/key/address/route/AllowedIPs/firewall conflicts and fail closed. Preserve unrelated VPN, WAN/LAN, DHCP/DNS, firewall, HotSpot, portal and voucher configuration. No script until fixed local commands and partial-failure behavior are reviewed.
3. **D1 credentials:** Demonstrate an attempt-bound authorization and bounded, nontruncated, schema-validated secret delivery over certificate-validated HTTPS. No passwords in QR, script/terminal, URL, file, logs, analytics or support evidence. Validate router trust roots/clock and actual Fetch behavior; never disable TLS checks or install an unreviewed CA to pass a test.
4. **S1 roles:** Create distinct per-router Monitoring and Safe Change identities. Prove Monitoring denies representative writes; Safe Change omits user-management privilege and is constrained by server-side operation allowlists/owner approval. RouterOS policy may not provide per-command isolation; a broad built-in group is not a workaround. Account for REST group-policy changes taking effect only after a session renews; emergency peer revoke/job cancellation cannot rely only on a group downgrade.
5. **Connection proof:** Verify fresh Hub-side WireGuard handshake, then a newer certificate-verified authenticated Monitoring read and router/site identity binding. A handshake/public key alone does not attest the physical device. Only then may the app show Connected.
6. **Recovery/revocation:** Test interruptions at each write boundary, partial-state readback, no blind rerun, targeted owner-approved cleanup of MikroMagic-owned objects, separate cloud peer revoke versus on-router cleanup, active REST session handling, R1/E1 emergency lock, and preservation of local customer service. WinBox Safe Mode is not transactional rollback.

D1 remains unresolved: local-admin visibility of credentials, terminal/history/file/log exposure, router-pulled credential delivery and least-privilege S1 behavior need hardware validation. First lab should be an isolated supported RouterOS v7/CHR or non-production device with no customer service, after separate approval. Do not use the production Hub, production keys or the owner's router-admin credential as a service identity.

## Owner evidence to provide after inspection

Return the sanitized facts from Stage 1 and whether the Mac had existing local WinBox access and whether the router serves customer traffic. Do not provide the RouterOS password, exported configuration, private keys or full unredacted screenshots. We will compare the evidence with the model-independent matrix and return a reviewed scope before requesting any configuration-change approval.

## Separate approvals

- **A:** physical read-only inspection only; no configuration changes.
- **B:** create/start the isolated local development Hub and test database after reviewing rendered isolation config; no production Hub/VPS changes.
- **C:** physical bootstrap/credential-provisioning lab only after D1 gates are technically resolved, with exact changes, backup/recovery, evidence and stop conditions.
- **D:** any later revocation/cleanup or additional Safe Change test not expressly covered by C.

This document authorizes none of those actions by itself.
