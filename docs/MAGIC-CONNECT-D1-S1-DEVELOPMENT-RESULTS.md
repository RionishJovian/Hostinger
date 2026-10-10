# D1/S1 software continuation — 2026-10-09

Project: `/Users/aces/MikroMagic-Build21-FrozenV1-v8-corrective`.
Notion authority: https://www.notion.so/3f2489e3dbb681cc9d2de66befe42255
Manual hardware inspection deferred by owner. No MikroTik or VPS contacted.

## Implemented, not deployed

- `backend/bootstrap_security.py`: fresh original-owner/scoped provisioning review,
  immutable plan-scope digest, two separate candidate policy sets, 4096-byte
  data-only envelope validator with duplicate-key/extra-field/role/binding/format/
  credential-reuse rejection and secret-redacted repr. No credential generator
  or delivery endpoint. Router dispatch ALWAYS raises the hardware-gate error.
- `backend/hubs.py`: successful owner enrollment includes that blocked review.
- Same module's automatic inspector: fixed GETs only, property-limited metadata,
  dedicated Monitoring credential, HTTPS mandatory, explicit unknowns and no
  Connected/S1-effective-permission claim. `scripts/inspect-routeros-security.py`
  is prepared for separately approved use, NOT executed. It cannot bypass
  missing credentials, bootstrap an unconnected router, or create a user.
- `backend/routeros_adapter.py`: password-safe repr, direct connections without
  environment proxies, no redirect following and sanitized TLS failure category.
- `backend/hub_orchestrator.py`: PostgreSQL same-plan row locking around peer
  operations/readback, including a fresh check after durable-claim commit. This
  corrects a reproduced in-flight add versus emergency-revoke race.
- `backend/magic_connect.py`: cancellation/expiry acquire fresh PostgreSQL attempt
  state before testing consumed authority. No new migration or features.
- Explicit code-only package allowlist now includes the imported security module;
  local databases, credentials and keys remain excluded from distribution.

## Actual integration evidence

Command: `.venv/bin/python scripts/run-enrollment-postgresql.py` (approved outside
the sandbox solely for native shared memory / private Unix socket support).

PASS, 11 tests. PostgreSQL **17.11**, head **032**, repeated upgrade no-op. New
cluster only, private 0700 parent/socket, no TCP listener, nonsuperuser application
test role, fresh synthetic records. No Homebrew service/default cluster used.
Result: `/private/tmp/mm-enroll-pg-udeof3_i/result.json`.
Protected diagnostic log and retained database remain alongside the result.
The lab server was stopped by its exact pg_ctl data-directory target; no data
directory or evidence was deleted. Earlier failed lab evidence is retained.

Coverage: unique bindings; authenticated two-plan/one-attempt race; same/different
idempotency keys; consumed-authority cancellation denial; cancel-versus-consume;
expired/closed/wrong-tenant rejection; durable-claim recovery; revoke-versus-add
and revoke-versus-recovery. Independent database connections/transactions, no
global request lock. **Hub side effects in these PostgreSQL tests are MOCK.**
Previous real Linux transport evidence is preserved, not rerun. DB-fixture account
passwords are random/in-memory only; no live data or historical credentials.

Regression command for software boundaries:

```sh
PYTHONPATH=.:tests .venv/bin/python -W ignore::ResourceWarning -m unittest test_bootstrap_security test_hub_orchestrator test_hubs test_routeros_adapter test_enrollment_migration test_wireguard_hub test_magic_hub_package
```

42 focused tests passed. Final full regression command:

```sh
PYTHONPATH=.:tests .venv/bin/python -W ignore::ResourceWarning -m unittest discover -s tests
```

Completed with localhost-fixture permission: **441 tests, OK (11 skipped)**,
151.065 seconds. This means 430 passed in that run; the 11 opt-in PostgreSQL
tests passed separately against real PostgreSQL as recorded above. Metadata/
envelope tests use synthetic fixtures; they are not RouterOS acceptance. The
existing Starlette/httpx deprecation and Alembic unnamed-check warning remain;
no unrelated dependency/schema changes were made.

REAL TLS command (localhost-only servers, synthetic ephemeral CA/certificates):

```sh
PYTHONPATH=.:tests .venv/bin/python -W ignore::ResourceWarning -m unittest test_bootstrap_tls_local
```

PASS: one test containing four real TLS cases—trusted SAN succeeds, untrusted CA,
wrong hostname and expired certificate rejected with `tls_verification_failed`.
RouterOS JSON response is synthetic; no RouterOS TLS implementation was tested.
The first synthetic certificate lacked AKI/SKI required by strict OpenSSL; the
fixture was corrected, not certificate verification relaxed.

## Remaining hardware boundary

NOT READY for executable bootstrap, automatic account provisioning or a
configuration-changing MikroTik connection test. Automatic read-only inspection
is ready only when an approved device already has a dedicated Monitoring identity
and trusted HTTPS. Its absence is a real prerequisite, not permission to use the
owner's administrator credential, disable TLS, or require initial remote preflight.

Need a separately reviewed isolated RouterOS lab scope to validate both TLS
directions, router-generated keys, separate device-enrollment capability, bounded
router-pulled secret handling, local-admin visibility, actual Monitoring deny tests,
Safe Change privilege/file limits, tunnel-only source restrictions, partial
creation/recovery and active-session emergency revocation. No scripts are issued
until these security gates are resolved. The no-egress Lima lab cannot simply
contact the physical router; host routes, bridges or services need approval.

Policy/Fetch basis: manufacturer [User](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User)
and [Fetch](https://help.mikrotik.com/docs/spaces/ROS/pages/8978514/Fetch) docs.
Candidate policies are hypotheses, not effective permission certification; no
claim of secrecy against a full local RouterOS administrator is made.

Original v8 ZIP hash reverified unchanged. Existing local SQLite databases,
Hostinger, public site and physical/historical tunnels untouched. Lima remains
running; sanitized readback confirms its two preserved synthetic peers.
