# MikroMagic Build 21 Launch Readiness

Updated 2026-10-10.

## 2026-10-10 corrective-source continuation

The current corrective source is ahead of the accepted private RC: migration
033 adds privacy-minimized signed-in-device and seven-day Owner/Admin login
history, and the Sites workspace now has a fail-closed first-site acceptance
coordinator. The coordinator is locally verified but cannot mark HotSpot apply,
test voucher, First Customer Test or Site Ready without real device evidence.
These changes have not been deployed to the private RC or a public host.

Current local verification: 464 Python tests pass with 12 environment-gated
skips; 34 JavaScript tests, responsive UI checks, production build and Sites
packaging pass. The API contract is regenerated. PostgreSQL schema compilation
passes, but full Alembic offline `--sql` generation is blocked by pre-existing
migration 029's data-dependent user lookup and is not claimed as a pass.

## 2026-10-09 isolated application release-candidate result

The **built** web client on loopback port 4173, the real FastAPI server on
loopback port 8788, and a fresh PostgreSQL 17 database on a private Unix socket
passed Chrome browser acceptance: platform/owner authentication, two-tenant
business and site creation, package creation, portal draft update, refresh and
re-login, cross-tenant denials, and the public Magic Connect fail-closed gate.
The reproducible runner is `scripts/verify-release-candidate-browser.mjs`;
private evidence is at `/private/tmp/mm-build21-rc.OMNgoh/browser-result.json`.
The database remains isolated and synthetic. This is **not** a public deployment
or RouterOS/HotSpot acceptance. Public deployment milestones remain zero.

Magic Connect pairing now defaults unavailable in the application UI and API.
Only the exact isolated development environment plus explicit test-mode flag
enables the existing internal pairing flow; bootstrap and Connected are still
not claimed. The earlier counts and external-blocker descriptions below are
historical 2026-10-07 notes, not current acceptance evidence.

## Verified locally

- Frontend production build and Sites packaging pass.
- Python regression suite: 279 tests pass.
- Managed-device inventory and topology limits are tested.
- Offline voucher event idempotency and conflict recording are tested.
- Incident creation/resolution and tenant isolation are tested.
- Backup metadata and restore-verification rules are tested.
- Firmware scheduling rules are tested.
- Provider callback HMAC helper is tested.
- OpenAPI contract has been regenerated through migration 025.

## Implemented foundations

- Three roles and tenant-scoped account workflows.
- Sites, MikroTik registry, Magic Hub management plans, captive portal, packages, vouchers, payment review, revenue and subscriptions.
- Site-scoped switch/AP inventory with configurable default limit of one switch and five APs.
- Durable offline voucher reconciliation records that never silently grant access.
- Evidence-labelled incident history.
- Backup/restore metadata with explicit encryption and verified-restore state.
- Staged firmware rollout plans with maintenance windows and adapter-pending state.
- Provider-neutral signed callback verification helper.

## External acceptance still required

### Current hard blocker

The workspace currently has no configured RouterOS endpoint/credentials, Magic Hub VPS endpoint/keys, or test-router LAN path. The Build 21 source also does not contain a live RouterOS/WireGuard command adapter; its current plans deliberately return `unverified`/`adapter_pending`. Therefore the MikroTik acceptance gate cannot be executed or marked passed from this workspace.

To execute that gate, the launch environment must provide a disposable test MikroTik, its RouterOS version and management path, a provisioned Magic Hub VPS, WireGuard peer keys, an approved command transport, and a test HotSpot interface with controlled guest clients. The test must capture enrollment, handshake, capability evidence, backup/diff, apply, post-change verification, rollback, voucher redemption, RADIUS/HotSpot accounting, time quota, data quota, combined quota, reconnect, and bypass behavior.

These cannot be honestly marked complete without the supplied infrastructure and credentials:

- Webapp VPS and Magic Hub VPS deployment.
- Real RouterOS enrollment, WireGuard handshake, capability discovery, apply, verification and rollback.
- Local HotSpot/RADIUS or User Manager accounting and data/time enforcement.
- Managed switch/AP vendor adapters and live telemetry.
- Payment provider or Telegram/Discord bot identity verification and outbound delivery.
- Encrypted backup storage and real restore execution.
- Firmware artifact distribution and device-specific upgrade/rollback.
- Jellyfin gateway, entitlement checks and real guest playback.
- Production PostgreSQL concurrency, TLS, mobile/browser, outage and recovery acceptance.

The application must remain labelled as development/integration-ready until those acceptance gates pass.
