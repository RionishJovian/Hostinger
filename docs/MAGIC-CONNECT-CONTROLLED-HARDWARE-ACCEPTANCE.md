# First controlled RouterOS acceptance procedure

Prepared 2026-10-09. PLAN ONLY: no hardware commands executed or changes authorized.
Project: `/Users/aces/MikroMagic-Build21-FrozenV1-v8-corrective`.
Authority: Notion requirements, including A/A1/A1.1/B1/C1/R1/E1/M1/S1/D1 and L46:
https://www.notion.so/3f2489e3dbb681cc9d2de66befe42255

The hAP ax2 is one acceptance sample, not the compatibility definition.
Previous Linux WireGuard, PostgreSQL and localhost TLS evidence is retained;
none establishes RouterOS credential security or physical connectivity.

## Stage 1 — Existing-access inspection; zero configuration changes

After separate permission to begin the hardware session, owner powers on the
router and opens the existing local WinBox session over the same cable/port.
No internet or dedicated management account is required for this stage.

1. Establish whether WinBox uses MAC or IP access, and whether actual window
   capture/control works. Window titles alone are not evidence of control.
2. If usable, inspect existing WinBox views directly, without Terminal scripts.
   Record only model/version/architecture, local management path, Wi-Fi uplink
   and route state, conflict metadata, HTTPS service/certificate metadata and
   dedicated-user/group presence. Do not open secret fields or full exports.
3. If UI automation is unavailable, owner opens the few necessary WinBox views
   (IP Services, Certificates, Users/Groups, and relevant network lists) during
   one guided session. Capture only cropped, sanitized metadata. Do not repeat
   the previous nine-command procedure or request admin credentials in chat.
4. Only if existing protected Monitoring credentials AND reachable trusted HTTPS
   already exist, use `scripts/inspect-routeros-security.py` for the fixed,
   property-limited GET inspection. Otherwise report that probe BLOCKED; do not
   substitute the owner's administrator password or disable certificate checks.

PASS: enough current evidence to specify an exact nonconflicting lab diff and
preserve the working local access path. FAIL: an observed unsafe conflict or
unexpected change. BLOCKED: necessary views/access cannot be inspected safely.
Read-only authentication may generate normal device access/audit events.

Initial enrollment has no authentication deadlock: local authorized WinBox
inspection and owner review precede remote verification. Missing remote trust
blocks automated management, not initial review. No Connected claim is made.

## Stage 2 — Temporary TLS/S1 lab; FIRST ROUTER-WRITE APPROVAL

Approval must name the resolved addresses, object names, certificate fingerprint,
service settings, rule positions and recovery diff from Stage 1. No wildcard
approval, executable bootstrap or secret-delivery claim is implied.

Conditional additions, only where missing and explicitly approved:

- A unique temporary management address on the existing Mac-facing Ethernet
  interface, plus an approved Mac address on a conflict-free direct subnet if
  WinBox currently has MAC-only access. No bridge, DHCP or default-route changes.
- A lab-only HTTPS server certificate with correct identity/SAN, protected key,
  and independently verified trust installed in the isolated test client.
  Enable/configure `www-ssl` only if safe; existing service users/certificates
  must not be displaced. Router-to-provisioner TLS trust is a separate test.
- Exact-source/interface/port management protection, including IPv6 exposure
  assessment. Restrict new test access to the Mac; preserve existing management
  users and access. Do not reorder or remove legacy firewall rules. If this
  cannot be achieved without changing unrelated access, STOP for revised scope.
- Two unique lab-only users and custom groups: Monitoring candidate `read,
  rest-api`; Safe Change candidate `read,write,rest-api`. No default full/read/
  write group reuse; no additional policy grants to make tests pass. Limit user
  source addresses to the approved test path.

Owner handles temporary lab passwords privately through trusted local UI and
protected test storage, never chat, script text, screenshots or logs. This is
an explicit lab setup exception, NOT implementation of technician-blind D1.
Production credentials are neither created nor used.

Automate trusted HTTPS metadata reads once prerequisites exist. Test untrusted,
wrong-identity and expired TLS rejection without changing the router clock.
Test Monitoring write denial, identity separation and prohibited user/group,
secret and file access using synthetic canaries only. Positive write tests
require a separately reviewed fixed-target disposable canary harness; no
arbitrary command endpoint and no writes to existing configuration. If that
harness is not ready, those tests remain BLOCKED, not inferred from flags.

PASS: validated TLS and observed permission boundaries meet the reviewed lab
criteria. FAIL: unauthorized access, secret leakage, TLS bypass or unrelated
write. BLOCKED: missing safe test path, global-service conflict, unsafe canary
test, or permissions too coarse to establish the required boundary.
Stage 2 can pass individual TLS tests while S1 remains FAIL/BLOCKED.

## Stage 3 — D1 confidential provisioning feasibility; separate write gate

Current code provides data-only review/validation, NOT a credential issuer,
delivery endpoint or enabled router provisioning dispatcher.

Before execution, implement/review a separate device-bound, single-use delivery
capability tied to owner approval, tenant/site/attempt/plan/Hub. The technician
pairing code is not this capability. Establish both TLS trust directions without
TOFU or disabling verification. Review RouterOS fetch response handling,
redirect rejection, bounded parsing, transient secret handling, logging,
interruption, expiry and recovery. No permanent password in technician-visible
text or URL; no historical keys or administrator-password reuse.

Use fresh lab identities only, with controlled local owner access. A full local
router administrator can inspect/reset credentials; do not promise protection
against that administrator. Define this trust assumption before the test.

PASS: real RouterOS demonstrates confidential delivery, correct separate
identities, single-use binding and safe partial-failure handling with sanitized
evidence. FAIL: leakage, replay, incorrect binding or insecure TLS. BLOCKED:
delivery implementation or safe permission boundary not established. Currently
BLOCKED; temporary manually created lab users do not make D1 pass.

## Stage 4 — Dedicated WireGuard bootstrap; separate network/write approval

Proceed only after the required security gates pass and the exact bootstrap is
reviewed. Use new uniquely named interface/peer, router-generated private key,
public-key-only registration, nonconflicting tunnel addresses, exact management
host routes/AllowedIPs and only explicitly approved management input rules.
Private key stays on router. Preserve the historical tunnel and all its peers,
addresses, routes and firewall rules. No default route, WAN, Wi-Fi mode, LAN,
DHCP, DNS, HotSpot or unrelated VPN changes.

The current isolated Lima lab is not automatically reachable from this router.
Approve an exact private development UDP path separately before execution;
no implicit VM bridge, host forwarding, public management listener or Hostinger
deployment. If no safe reachable development endpoint exists, stage BLOCKED.

Owner uses existing authenticated pairing and reviews the exact plan; technician
access alone cannot provision a peer. Inspect conflicts immediately before any
write. On partial completion, stop and read back owned objects; never blindly
repeat or remove similarly named legacy objects.

PASS: correct owned additions and fresh handshake with the assigned development
Hub. FAIL: conflicts, unintended changes, identity mismatch or unauthorized
peer. BLOCKED: security prerequisites, reviewed bootstrap or safe network path
missing. Handshake alone means management verification pending, not Connected.

## Stage 5 — Authenticated verification and emergency recovery acceptance

Using the Monitoring identity over validated HTTPS through the dedicated tunnel,
verify device identity privately against the owner-bound enrollment and perform
capability-based authenticated read-only preflight. Enforce fresh evidence before
later Safe Change operations. Test Safe Change only within separately approved
canary scope, never HotSpot or customer-network settings.

Explicitly test target peer revocation/security lock, denial of further management
and preservation of unrelated peers and local connectivity. Revocation is a
state-changing test needing approval. Record inability to verify customer Wi-Fi
honestly when management is lost. Do not automatically restore revoked trust.

PASS: fresh handshake AND authenticated identity-bound router read; effective
S1/D1 and recovery gates separately supported by evidence. FAIL: unauthorized
access, stale/mismatched identity or damage to existing connectivity. BLOCKED:
any required gate unavailable. Never infer hardware success from mocked output.

## Recovery, stop conditions and minimum owner actions

Before each write stage, retain a protected local baseline and exact object IDs,
old settings and ordered rollback diff. Any configuration backup requires its
own explicit inclusion in the approval and private handling. Evaluate Safe Mode
for that bounded session; it is not proof of atomic rollback or credential erasure.

On failure, stop writes; preserve evidence and local WinBox. Disable affected
new lab access/revoke only its development peer where authorized, inspect state,
then remove only verified lab-owned additions under the approved rollback scope.
Restore only specific changed service values. Remove lab certificates last after
confirming no dependency; revoke temporary credentials and remove protected secret
copies under the agreed recovery scope. No reset, reboot, full restore, broad
cleanup or legacy tunnel repair. Loss of local access requires owner-assisted
local recovery, not automatic WAN/firewall experimentation.

Owner actions: power on/connect/login once for Stage 1; help open views only if
computer access fails; approve the resulting exact Stage 2 diff; handle lab secrets
privately; separately authorize D1, bootstrap/network and revocation stages when
their gates are ready. No nine-command block and no administrator password sharing.

Ready to propose Stage 1 only. NOT READY for an executable Magic Connect bootstrap.
No application code, database, router, VM networking, VPS or original ZIP changed
by preparation of this document.
