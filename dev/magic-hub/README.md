# Isolated REAL WireGuard acceptance — approval required

This is NOT a RouterOS bootstrap, public Hub, or deployment. No real hardware
or historical credentials are used. Software preparation alone is not a PASS.

## One bounded prerequisite approval

Install Homebrew `lima` and its required dependencies; create and start exactly
one new ARM64 VZ VM named `mikromagic-wg-dev` from `dev/magic-hub/lima.yaml`.
Reserve 2 vCPUs, 2 GiB RAM, a 10 GiB sparse disk, and image/package downloads.
No Docker Desktop, existing VM, privileged networking helper, bridged network,
host interface/route/VPN changes, or shared host filesystem is required.
Lima's VM control transport is private; no application forwarding is enabled.
Check merged Lima configuration (including any global defaults) before start.
STOP if it adds host mounts, agent forwarding, bridged networking or public ports.

Proposed commands AFTER approval, not executed during preparation:

```sh
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install lima
limactl create --name=mikromagic-wg-dev dev/magic-hub/lima.yaml
limactl list --json
# Inspect the created instance's full lima.yaml before starting it.
limactl start mikromagic-wg-dev
limactl shell mikromagic-wg-dev sudo apt-get update
limactl shell mikromagic-wg-dev sudo apt-get install -y --no-install-recommends wireguard-tools iproute2 iputils-ping python3-venv
# In the new guest-only code directory:
python3 -m venv venv
venv/bin/pip install --disable-pip-version-check SQLAlchemy==2.1.3
```

Use Ubuntu 24.04's image template, verify the resolved image's configured digest
and download verification; never skip image integrity verification. Validate
actual installed Lima schema and rendered configuration before VM execution.
Guest networking is needed for packages only. The test endpoints have no
default routes and no connection to the guest main network or host LAN.

Generate `scripts/package-magic-hub-test.py`'s code-only bundle and independently
verify its `files.sha256` and archive digest. Transfer ONLY that bundle with
`limactl copy`; no source databases, .env, credentials or keys. Extract into a
new guest-owned private directory (never overwrite previous evidence). Make the
root-owned marker `/etc/mikromagic-wg-development` contain `mikromagic-wg-dev`
only after verifying the VM identity. Run its harness with guest sudo:

```sh
sudo /path/to/new/code-only/venv/bin/python /path/to/new/code-only/scripts/verify-real-wireguard.py
```

The test creates Linux kernel WG interfaces inside two NEW dedicated network
namespaces, connected only to each other by veth. Keys are newly generated in
each namespace and stored root-only under `/run`; raw subprocess output is
never logged. Interfaces are exactly `mm-dev-hub` and `mm-dev-peer`.

Evidence gates: real adapter/orchestrator peer add, idempotent readback, actual
fresh handshake, bidirectional ping and encrypted counters, conflict rejection,
peer removal/readback, emergency lock and traffic denial. Synthetic lifecycle
records use a new guest-only SQLite DB. This tests Linux WireGuard transport,
NOT PostgreSQL concurrency or RouterOS management. No `Connected` claim is made.

No automatic namespace/volume/VM cleanup. On any failure preserve the evidence
and stop. A second run must use an explicitly reviewed cleanup or fresh VM;
never remove a pre-existing namespace automatically.

## Enrollment integration and hardware boundary

Migration 032 adds a unique pairing-to-plan binding (no existing DB migrated).
The owner binds their approved, unexpired attempt to a reviewed plan/site and
assigned Hub. The orchestration claim is committed before any host mutation;
interruption requires readback. Recovery preserves the consumed idempotency key.
Pairing cancellation cannot silently revoke consumed peer authority: use the
auditable emergency peer lock. Host operations remain disabled by default.

The independently owner-reviewed hardware-identity digest is immutable in the
binding; missing/mismatched identity never verifies management. This is a
consistency check, not device attestation. The expected identity must NOT be
learned from the same remote response it is meant to verify.

D1 credential provisioning and S1 least-privilege RouterOS permission tests
remain hardware-blocked. No executable RouterOS bootstrap is emitted. After
Linux transport acceptance, separately approve a read-only router capability
and certificate-trust review, then a narrowly reviewed non-conflicting tunnel
only once secure credential provisioning has been demonstrated. Preserve the
existing hAP ax² tunnel and all WAN/LAN/HotSpot/VPN settings.

Source references: https://lima-vm.io/docs/config/ and
https://www.wireguard.com/netns/ . No paid service required.

## Actual approved execution — 2026-10-09

REAL runtime acceptance: PASS. Lima 2.2.1 / ARM64 VZ / Ubuntu 24.04 /
Linux 6.8.0-142-generic / wireguard-tools 1.0.20210914 / SQLAlchemy 2.1.3.
Only `mikromagic-wg-dev` was created and started (2 CPUs, 2 GiB, 10 GiB).
The image was independently verified as
`1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55`.

Actual effective config and running guest checks: no host mounts, no additional
networks, no containerd, no forwarded host proxy environment, and no application
port forwarding. Lima control SSH binds `127.0.0.1:64636` only. Each test netns
contains only loopback, its dedicated veth endpoint and WireGuard interface;
neither namespace has an IPv4/IPv6 default route or a connection to the guest's
main network. The source config now pins only the verified image (no fallback).

The exact executed code bundle SHA-256 is
`e7009584ad5a086aa5c59850a6e1a8ca670544cf40efc198416ca37bc5145dbe`;
its ten-record file manifest SHA-256 is
`02690a032bd6a8dab5bc48e480abb8af3ddcea5dfd2f7f52e05baea2127b56f6`.
All ten files verified inside the VM before execution. No application code was
changed to obtain a PASS. Ubuntu's packaged SQLAlchemy 1.4 was insufficient;
the exact application version was installed into a new guest-only venv instead.
The unused apt package remains in this disposable guest; no cleanup was done.

Execution command (completed once):

```sh
limactl shell mikromagic-wg-dev sudo /var/tmp/mikromagic-wg-code.12qXAp/venv/bin/python /var/tmp/mikromagic-wg-code.12qXAp/scripts/verify-real-wireguard.py
```

Real evidence: peer provision/readback, idempotency, interrupted-claim recovery
against the actual kernel peer, missing-interface failure, conflict rejection,
fresh handshake, bidirectional ping, positive encrypted RX/TX, removal/readback,
emergency revocation and traffic denial all passed. Post-test peer-side counters
were RX 860 / TX 2384 bytes; handshake epoch 1791531584. The Hub had zero peers
after emergency revocation. The Linux transport never reported RouterOS Connected.

Interruption itself was deliberately simulated by setting the synthetic plan's
pending state; recovery readback was REAL. No OS process crash or RouterOS
failure recovery was proven. HTTP owner authentication/pairing remains separately
software-tested; this runtime used a synthetic approved enrollment record and
the actual current Hub orchestrator. PostgreSQL concurrency is not tested here.

Root-protected guest evidence: `/var/tmp/mikromagic-wg-evidence-bcins51p/result.json`.
A sanitized local copy is `/private/tmp/mikromagic-real-wireguard-result-20261009.json`.
VM, namespaces and protected synthetic test keys remain preserved; the Hub peer
is revoked. No existing local DB, Docker environment, VPS, physical router or
original ZIP was changed. Do not rerun into the existing namespaces automatically.

## Authenticated pairing → actual development Hub — 2026-10-09

PASS: actual password login, technician claim, original-owner approval, immutable
tenant/site/plan binding and assigned-Hub verification now reach the real kernel
adapter through the application routes. No HTTP listener was started: FastAPI's
in-process ASGI client runs inside the existing no-egress `mm-wg-hub` namespace.
This is API integration, not browser acceptance or RouterOS verification.

Code changes tighten attempt ownership and independently compare the allowlisted
interface's actual public identity with its assigned Hub record before operations.
Default production host-operation flags remain disabled. No new migration.

The first run preserved all successful negative checks but stopped at an expiry
assertion. Diagnosis: the test patched `time.time`, whereas the orchestrator's
default argument retained its original function. The operation occurred before
real expiry; this was inconsistent fixture clocks, not evidence of an expiry
bypass. Both layers now share a dynamically injected controlled clock. A focused
continuation completed only outstanding gates in the same synthetic DB/VM. It
privately rotated only two synthetic fixture passwords and used actual login;
no session/token was inserted to bypass authentication. Previous evidence stayed
unchanged. The initial guard and fixture peer remain preserved, with no endpoints.

New deterministic 47-file code-only bundle (verified again inside the guest):

- Archive SHA-256: `68db5112c247d440ba5052a5b14fda2ed054f564380108a9dd744a925730d001`
- File manifest SHA-256: `8ad865c71c8f130d7a9eade881239a500e90187258cbd40b60624be14e26af29`
- Guest snapshot: `/var/tmp/mikromagic-pairing-continuation-code.t8LkUp`

Completed command:

```sh
limactl shell mikromagic-wg-dev sudo ip netns exec mm-wg-hub /var/tmp/mikromagic-wg-code.12qXAp/venv/bin/python /var/tmp/mikromagic-pairing-continuation-code.t8LkUp/scripts/resume-pairing-real-hub.py /var/tmp/mikromagic-pairing-evidence-jkvlrtsl
```

Result: exact 600-second expiry and expired technician token rejected; one
authorized kernel peer add/readback; idempotent retry with no second write;
different-key replay rejected; interrupted-state recovery reads the actual peer;
cross-tenant revocation rejected; owner emergency lock removes only the target;
locked peer cannot be reprovisioned; consumed authority, milestones and audit
chain persist. Two real mutations total: add and revoke. No handshake/traffic
tests repeated. Kernel observation never claimed Router Connected.

Sanitized evidence (raw credentials/keys/DB never copied to the Mac):

- Initial stopped run: `/private/tmp/mikromagic-pairing-real-hub-initial-20261009.json`
- Completed remaining gates: `/private/tmp/mikromagic-pairing-real-hub-continuation-20261009.json`
- Guest completion: `/var/tmp/mikromagic-pairing-continuation-9k8z1r7u/result.json`

Post-run isolation: zero host virtiofs/9p mounts; neither namespace has IPv4/IPv6
default routes; Hub namespace has no TCP listener; Lima control SSH remains
localhost-only. No new VM, interface, service, public port or external connection.

Remaining: PostgreSQL enrollment-claim concurrency; real RouterOS TLS/identity
reads; D1 secure credential delivery; S1 separate least-privilege Monitoring/Safe
Change permissions and device-side recovery. A separate approved read-only
hardware feasibility session is the next step, NOT bootstrap/configuration.

Regression verification for this snapshot: focused six-module suite 36/36 PASS.
Full `PYTHONPATH=. .venv/bin/python -W ignore::ResourceWarning -m unittest discover
-s tests` ran 416 passing tests but reported one `test_api.WorkflowTests`
setup error: the sandbox denied its temporary localhost socket bind. Only that
blocked class was rerun with approved escalation using `PYTHONPATH=.:tests
.venv/bin/python -W ignore::ResourceWarning -m unittest test_api`; all seven
tests passed. Aggregate exercised coverage is 423 passing tests across those
runs, not a single uninterrupted full-suite PASS. No frontend source changed.
The Starlette/httpx deprecation and Alembic unnamed-check warning remain noted;
no unrelated dependency/schema refactor was performed.
