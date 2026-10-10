# Magic Connect D1/S1 hardware feasibility — prepared, NOT executed

2026-10-09. READY for a separately approved read-only inspection; NOT READY for
credential provisioning, bootstrap or a configuration-changing connection test.
Authority: [frozen Notion, including S1/D1 and L45](https://www.notion.so/3f2489e3dbb681cc9d2de66befe42255).
Project: `/Users/aces/MikroMagic-Build21-FrozenV1-v8-corrective`.
The hAP ax² / reported RouterOS 7.24.2 / ARM64 is one test sample, not a platform
compatibility definition. All current hardware findings below are UNOBSERVED.

## One consolidated owner-led procedure — after separate approval only

1. Power on only after approval. Keep the existing cabling and trusted local
   WinBox access; no Internet uplink is needed for this inspection. Never assume
   ether1 is the uplink. Use the existing local login; do not send its password.
2. Confirm nobody else is editing the router. If customer service is active,
   stop before any later change testing. Do not use Safe Mode as a substitute
   for approval. Do not run Fetch, HTTPS probes, REST requests, scripts, imports,
   exports, file reads or WireGuard commands in this session.
3. In WinBox Terminal run the following ordinary read-only commands individually
   in order. This block is a checklist, NOT an executable bootstrap/script.
   Keep raw output local: service ACLs, certificate names and comments can contain
   identifying data. If a menu/property is unsupported or access is denied,
   record UNAVAILABLE and continue only with remaining listed reads; never
   enable a service, increase permissions, or substitute a configuration dump.

```routeros
/system clock print
/ip service print detail without-paging where name="www-ssl"
/ip service print detail without-paging where name="www"
/ip service webserver print
/certificate settings print
/certificate print without-paging
/user group print detail without-paging
/user print count-only where name~"^mm-monitor-"
/user print count-only where name~"^mm-safechange-"
```

4. Inspect only the certificate already referenced by `www-ssl` in WinBox
   System → Certificates. View properties, then close with Cancel/Escape; no
   Apply/OK edits, import, export, signing or private-key operation. Locally
   compare validity dates to the Mac's independently known time, `tls-server`
   usage, issuer/chain, presence of its private-key flag, and SAN against the
   intended *later* HTTPS name/IP. If that destination is not yet defined, SAN
   matching is UNKNOWN. Send only aliases/booleans, not CN/SAN, fingerprints,
   certificate serial numbers, keys, screenshots or actual endpoint addresses.
5. In WinBox System → Users, view the list and group membership only. Record
   whether relevant dedicated accounts are active, distinct, which aliased
   groups they use, and whether login addresses are unrestricted or restricted.
   Do not open password-changing controls or print user details/active sessions.
   The two count commands detect the current app's naming convention only;
   zero matches does not establish absence of older accounts with other names.
6. Stop. Return only the sanitized template below. Preserve all configuration,
   including legacy WireGuard, Wi-Fi uplink, management access and existing users.
   Do not run a follow-up connectivity test without separate authorization.

Why these reads: clock/CA settings characterize outbound certificate validation;
`www-ssl` plus webserver settings characterize HTTPS REST prerequisites; `www`
identifies plaintext REST risk; certificate metadata characterizes server trust;
groups/membership characterize proposed identity separation. REST uses
`www-ssl`, not the separate binary `api-ssl` service. A service ACL is NOT proof
of firewall reachability or Internet exposure. No routes/firewall need re-auditing
for this narrowly scoped metadata session.

### Sanitized return template

- Sample: RouterOS version/architecture; any change from reported version.
- Clock: plausible / offset detected / unknown (no clock adjustment).
- HTTPS REST: service enabled/disabled/unknown; numeric port; rest-secure
  enabled/disabled/unavailable; ACL unrestricted/restricted/unknown.
- Plain HTTP: enabled/disabled/unknown; rest-plain enabled/disabled/unavailable.
- HTTPS certificate: assigned/missing; valid dates yes/no/unknown; server usage
  yes/no/unknown; key present yes/no/unknown; chain reviewed yes/no; destination
  SAN match yes/no/unknown. Alias certificates C1/C2; do not send raw details.
- Outbound Fetch trust: builtin-trust-store scope, CRL settings, relevant CA
  metadata available/absent/unknown. No claim of successful TLS validation.
- Groups: aliases G1/G2 and policy flag names only; no comments or personal names.
- Dedicated users: Monitoring/Safe Change count, distinct yes/no/unknown,
  enabled yes/no, group aliases, address restriction category only.
- Unsupported commands/access denial: menu and error category only.
- Configuration changes: NONE. Router connection: NOT VERIFIED.

## Acceptance checklist: PASS / FAIL / INCONCLUSIVE

Grade only the claim actually observed; missing configuration is a failed
prerequisite for the proposed path, NOT a failed Magic Connect deployment.

- Inspection boundary: PASS if only the listed reads/views occurred and local
  management stayed available; FAIL if any unapproved mutation occurred.
- HTTPS prerequisites: PASS (metadata only) if HTTPS REST is enabled with a
  suitable assigned, currently valid server certificate; FAIL if demonstrably
  absent/disabled/expired; INCONCLUSIVE for missing visibility or unknown SAN.
- Trust prerequisites: PASS (metadata only) if clock and candidate CA/service
  scope are suitable; FAIL for a demonstrated mismatch; INCONCLUSIVE for missing
  information. Actual chain/hostname/negative-certificate tests are INCONCLUSIVE
  until a separately approved TLS exchange. A trusted flag alone is not proof.
- S1 configured separation: PASS (metadata only) if distinct restricted accounts
  and reviewed custom groups exist; FAIL if the same account or broad default
  group is proposed for both roles; INCONCLUSIVE if accounts are absent or their
  intended use is unknown. Legacy accounts are not adopted or modified.
- S1 effective enforcement: INCONCLUSIVE in this read-only session. No write
  denial, file confidentiality, user-management denial or backend-secret process
  separation is proven by inspecting flags or using an administrator session.
- D1 provisioning: INCONCLUSIVE/BLOCKED until the approved lab demonstrates
  confidential delivery, bounded parsing, device/attempt binding and partial
  failure recovery. No production-readiness or Connected result is possible here.

RouterOS custom policy candidates for LATER testing only: Monitoring `read,
rest-api`; Safe Change `read,write,rest-api`, with no `policy`, `password`,
`sensitive`, `ftp`, `test`, `sniff`, reboot or interactive-login rights unless a
specific required operation is independently justified. These are hypotheses,
NOT account creation commands or proven permission boundaries. Manufacturer
documentation warns that the built-in `read` group is broad and all groups have
file access. Removing `ftp`/`sensitive` must not be presented as a complete file
or secret-isolation solution. `write` is broad; backend operation allowlists do
not constrain an attacker who steals the RouterOS credential itself.

## D1 evidence-based candidate plan — design only, still blocked

1. Keep the 10-minute owner/technician handoff separate from a new single-use
   device enrollment capability bound to exact owner/tenant/site/attempt/reviewed
   plan/Hub. The latter is not yet a demonstrated RouterOS delivery mechanism.
2. Only after later approval and collision inspection, router generates its WG
   private key locally and registers only the public key over validated HTTPS.
   A fresh handshake proves key control, not physical-device attestation.
3. Explicitly resolve BOTH TLS directions: router → enrollment server requires
   correct time, approved CA roots, hostname validation and no unchecked
   redirects; Hub → RouterOS requires an independently authenticated router
   certificate chain/SAN and protected CA reference. An unverified certificate
   learned from the same connection is not trust. The existing adapter supports
   HTTPS and a protected `ca_bundle`; no HTTP lab override is permitted here.
4. Proposed router-pulled response contains data only: two distinct server-
   generated credentials, exact account/group identities, attempt binding and
   bounded schema. Never cloud-returned executable code. No permanent passwords
   in script text, QR, URL, terminal output, files, logs, support or browser data.
   Require strict length/completeness checks (Fetch has bounded response buffers),
   no persistence of the response, no redirects to another origin, and explicit
   single-use/retry semantics. No operational Fetch command is supplied today.
5. Legitimate local privilege is needed to create accounts; do not leave a
   permanent bootstrap admin. Reject claims of secrecy against a malicious full
   RouterOS administrator: that person can inspect/reset accounts or intercept
   execution. The intended claim is absence of *incidental* reusable-secret
   exposure, not protection from the router administrator. If the product
   threat model requires the latter, STOP for a security decision.
6. Keep Monitoring and Safe Change secrets in separately authorized encrypted
   storage/process boundaries. Current separate credential loaders are a software
   foundation, NOT proof of a deployed encrypted store or process isolation.
   Router group/file behavior and credential redaction require negative tests.
7. Later lab must test actual Monitoring reads and representative denied writes,
   Safe Change user/privilege-change denial, source limitation, trusted TLS plus
   bad-chain/expired/wrong-host rejection, truncation and secret leak cases, partial
   account creation and retry recovery, and revocation with existing REST sessions.
   Treat cached-session permission effects as unverified device behavior, not a
   guaranteed ten-minute expiry. Emergency lock must revoke the Hub peer/block
   new jobs rather than rely only on changing RouterOS group policy.
8. Connected remains gated by fresh Hub handshake AND a newer authenticated,
   TLS-verified, independently identity-bound Monitoring read. No Linux result
   satisfies this RouterOS gate. Preserve customer/legacy configuration throughout.

All account/group/certificate creation, TLS/network exchanges, tunnel/config
changes, privilege-denial experiments and partial-failure tests need separate
explicit scope approval. The existing no-egress Lima transport lab cannot reach
this router; no bridge/route/public endpoint change is implicitly authorized.

## Separate pending gate: PostgreSQL enrollment concurrency

Do not repeat the already accepted authentication-lockout concurrency suite.
Use a newly approved disposable PostgreSQL database, synthetic tenants/accounts/
keys, migrations through 032, independent connections and real transactions;
never an existing local app DB, live VPS DB or SQLite as proof. No environment
is created or server started by this preparation task.

Required acceptance:

- Race two plans binding the same attempt: one binding, other rejected; unique
  attempt/plan constraints and rollback leave no partial authority.
- Race same-key provisions: one durable claim and one adapter mutation; the
  loser safely reports in-progress/replay, not a second write.
- Race different operation keys: one winner, conflict for the other; no extra
  peer or address allocation. Independent address allocations remain unique.
- Expiry/cancel/deny versus consume: serialize on attempt authority; an operation
  must not consume closed/expired authority. Cancellation after consumption must
  be rejected in favor of explicit revocation. Define the transaction boundary.
- Concurrent emergency lock versus provision/recovery: final kernel and DB state
  must not resurrect a locked peer; retain durable lock intent on interruption.
- Crash after claim/before or after side effect: restart requires actual readback,
  keeps operation identity and audit, never blindly reapplies or double-consumes.
- Wrong tenant/site/owner/Hub cannot win any race; fresh independent reads verify
  audit and consumed milestones after rollback/restart.

First verify DB behavior with a counting adapter (MOCK), then only if separately
approved exercise the existing allowlisted Linux Hub adapter with fresh synthetic
peers (REAL kernel, not RouterOS). Tests must not hold the whole request under a
global lock that hides DB races. Record each outcome and leave failures/evidence
intact; do not silently patch the implementation during acceptance.

## Remaining prerequisites — 2026-10-10

Reconciled against the owner-led Stage 1 GUI inspection of 2026-10-09
(`~/MikroMagic-stage1-2026-10-09.md`). That inspection used WinBox views only; the
read-only Terminal checklist above was not run. No router was contacted for this
reconciliation.

Already observed on the sample (sanitized):

- RouterOS 7.24.2 stable, ARM64, `wifi-qcom` package; one historical WireGuard interface.
- HTTPS REST prerequisite: **FAIL (absent)**. `www-ssl` is disabled/invalid. This is a
  missing prerequisite, not a failed Magic Connect deployment.
- Plain HTTP `www` (port 80) is enabled; `rest-plain` state unknown. `api-ssl` has no
  certificate (not used by REST). All service source ACLs are blank.
- Users: the owner administrator in `full`, plus one legacy MikroMagic automation
  account restricted to `10.77.0.9` whose group includes `policy`, `sensitive`, `ftp`,
  `test`, `reboot` and `write`. No distinct Monitoring or Safe Change identity was
  visible. S1 configured separation: **not present**. The legacy account must not be
  adopted or modified.
- IPv6 link-local addresses exist with no IPv6 input filter.

Still unknown (needs approval A, read-only): router clock/NTP state; certificate
store and trust settings (`builtin-trust-store`, CRL); webserver `rest-secure`
settings; definitions of groups other than the automation group; the two
`count-only` naming checks.

Remaining prerequisites, by kind:

1. Software, needs implementation authorization (no hardware):
   - A single-use device-enrollment capability distinct from the 10-minute pairing code.
   - A credential issuer and bounded, data-only delivery endpoint (deliberately absent today).
   - A fixed-target disposable canary harness for S1 positive write tests.
   - Close the legacy staff-authority gap recorded in `REQUIREMENTS-GAP.md`: a legacy
     `manager` staff account can currently create router plans and perform the owner's
     initial bootstrap review. Enrollment authority must be Owner/Admin-only before any
     real enrollment.
2. Owner decisions:
   - Accept or reject the stated trust limit: no secrecy against a full local RouterOS
     administrator (D1 candidate plan, item 5). Rejecting it is a STOP.
   - The HTTPS identity (name or tunnel address) the router certificate must carry.
     Once transport exists, `10.254.0.2` over the tunnel is a candidate that avoids a
     new Ethernet management address; this is not decided.
3. Router writes, controlled-acceptance Stage 2 approval: a lab-only server certificate
   and `www-ssl`, source-restricted to the approved test path; two lab users with custom
   groups (`read,rest-api` and `read,write,rest-api`).
4. Hardware tests after item 3: trusted/untrusted/wrong-host/expired TLS; Monitoring
   write denial; Safe Change user/privilege-change denial; REST session behaviour after
   group changes; partial account creation and recovery; then D1 delivery (Stage 3).

The transport-only Stage 2 in `MAGIC-CONNECT-TRANSPORT-LAB.md` does not depend on these
items. Its result is Transport Verified only, never Connected.

## Sources reviewed (documentation is not hardware evidence)

- [Notion authority, L45/S1/D1](https://www.notion.so/3f2489e3dbb681cc9d2de66befe42255)
- [MikroTik User policy and limitations](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User)
- [MikroTik Services and webserver settings](https://help.mikrotik.com/docs/spaces/ROS/pages/103841820/Services)
- [MikroTik Certificates, trust-store and validity](https://help.mikrotik.com/docs/spaces/ROS/pages/2555969/Certificates)
- [MikroTik Fetch, certificate checks and bounded output](https://help.mikrotik.com/docs/spaces/ROS/pages/8978514/Fetch)
- [MikroTik REST authentication](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API)
- [MikroTik console read-only print syntax](https://help.mikrotik.com/docs/spaces/ROS/pages/8978498/Console)

Preparation only: no router command, VM test, network probe, server startup,
secret generation, infrastructure access or application source change performed.
