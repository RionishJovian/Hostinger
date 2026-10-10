# Build 21 public-launch preparation

Status: proposal only. No public infrastructure was changed. The accepted
private RC remains at `/opt/mikromagic-build21-rc`; the changes currently in
this source tree have not been deployed to it.

## Launch decision

Do not expose the current RC publicly. The private deployment milestone passed
on 2026-10-09, including migrations through 032, real browser/API/PostgreSQL
flows, authentication and tenant isolation, and an isolated backup/restore
check. That proves the private RC only.

The first deployable public scope should be limited to the demonstrated
owner-facing account/onboarding, site, package, and portal editing/readback
flows. Treat voucher sales/fulfillment, payment processing, reporting, device
telemetry, HotSpot enforcement, and all router management as unavailable until
each has its own frozen-v1 acceptance evidence. Show unavailable states rather
than implying that an adapter or router action succeeded.

## Remaining launch gates

1. The intended public hostname is now `megamagic.tech`. DNS control, the exact
   apex/`www` behavior and public cutover remain unverified and unapproved.
   `mikromagic.com` is retired and must not be used.
2. Build the separate immutable public-test artifact from the current
   corrective source with `scripts/package-hostinger-public-test.py`, including
   migrations through 034 and the database-backed readiness endpoint. Record
   its SHA-256 and image digest. Do not alter the accepted RC artifact or
   promote its mutable database as production data.
3. Reconcile the currently running public Caddy container's mounted config and
   ingress Docker network, then approve one hostname-only route. Public ports
   80/443 remain owned by that existing ingress; do not add a listener or
   public port. The deployment's web container will join only the verified
   ingress network; API and PostgreSQL remain on private networks.
4. Re-accept the separate public-test candidate with migrations 033 and 034,
   including signed-in session/login history and the proposal-only HotSpot plan.
   This local implementation and its PostgreSQL tests are not evidence that
   either migration has run on the private RC or any production database.
5. Agree the initially enabled customer workflow and complete its acceptance.
   The private RC evidence covers onboarding, site/package creation, portal
   draft persistence, refresh, sign-out/re-login, anonymous denial,
   cross-tenant denial, and Magic Connect denial; it does not establish that
   every frozen-v1 business function is customer-ready.
6. Provision and test production-only secrets, backup destination, monitoring,
   HTTPS issuance/renewal, and rollback before routing public traffic.

## Proposed isolated deployment

- VPS: existing `srv2032937.hstgr.cloud`, directory
  `/opt/mikromagic-build21-prod`; do not touch `/opt/mikromagic-build21-rc` or
  any existing stack other than the approved Caddy route/reload.
- Compose project: `mikromagic-build21-public-test`; unique containers
  `mikromagic-build21-public-test-{db,migrate,api,web}-1`, private database and API,
  new `postgres_data` and encrypted-backup volumes, and a new private network.
  `web` alone joins the already-existing Caddy ingress network. No host port
  binding is needed; no database/API port is published.
- PostgreSQL 17, a separate database/role, fresh public-test-only credentials,
  and migrations through 034. Run migration as a one-shot operation before
  starting the app; stop on any migration error and preserve all volumes.
- Build/pin the application image from `release/mikromagic-build21-public-test.zip`.
  Keep `MIKROMAGIC_MAGIC_CONNECT_TEST_MODE=false`,
  `MIKROMAGIC_ENVIRONMENT=production`, RouterOS writes disabled, and do not
  mount router credentials or Hub keys.
- Keep pairing, enrollment, provisioning, safe-change worker, and unverified
  RouterOS management unavailable. Public acceptance must verify both UI
  disabled state and API capability denial; no Connected state without the
  required real handshake plus authenticated identity-bound management read.

## HTTPS and ingress

After the owner verifies DNS control and explicitly approves the route, add a
single hostname block to the existing Caddy configuration (using its verified
container-reachable service name on the verified shared ingress network):

```caddyfile
megamagic.tech {
    encode zstd gzip
    reverse_proxy mikromagic-build21-public-test-web:80
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }
}
```

Caddy's automatic HTTPS should obtain and renew the certificate after the
owner-controlled DNS points the selected hostname at this VPS and inbound 80/443
are confirmed by the owner. Keep HSTS disabled until valid HTTPS and renewal
are verified; evaluate CSP in report-only mode against the real UI before
enforcing it. Back up the exact Caddyfile and validate it before reload. Never
replace the whole file. The DNS state, apex/`www` behavior, TLS contact/renewal
owner, Caddy config path, and ingress network are intentionally unresolved—not
assumed.

## Secrets and backup/recovery

- Generate independent production database, session/cryptographic, and backup
  encryption secrets on the VPS. Deliver them only into a root-owned
  `/opt/mikromagic-build21-prod/secrets` directory (mode 0700); files mode 0400,
  readable only by the service identity that needs each secret. No source,
  ZIP, shell arguments, Compose interpolation output, logs, or evidence bundle
  contains secret values. A production session-signing/encryption secret must
  be separate from RC and historical deployments.
- Use a separate owner-approved off-host encrypted backup destination. Proposed
  schedule: daily encrypted PostgreSQL custom-format backup; retain 7 daily,
  4 weekly, and 3 monthly copies. Alert on failed/stale backups and verify each
  file's checksum and `pg_restore --list`. This policy and storage spend need
  owner approval before scheduling.
- Recovery drill: decrypt one selected backup only into a newly named,
  isolated temporary PostgreSQL database/container; restore, compare migration
  version and synthetic/approved aggregate checks, verify application can read
  it, then retain evidence and remove only that explicitly named temporary
  test resource after approval. Never restore over the live database as a test.
- Incident rollback: first stop public traffic by reverting only the new
  hostname route and reloading validated Caddy config; leave production
  containers, database, volumes, and backups intact for diagnosis. If app
  rollback is required, pin the previous approved image and roll back code
  without downgrading schema. For an incompatible migration, keep traffic
  disabled and use a reviewed restore of the matching pre-migration backup;
  preserve post-backup writes and obtain owner approval before any destructive
  database restoration.

## Monitoring and acceptance

The API now has separate liveness (`GET /v1/health`) and readiness
(`GET /v1/ready`) endpoints; readiness executes `SELECT 1` and returns only a
generic 503 on database failure. Container health should use readiness. Monitor
external HTTPS availability, readiness, 5xx rate, CPU/memory/disk, PostgreSQL
availability, backup age/checksum, TLS expiry/renewal, and Caddy errors. Do not
log bearer tokens, passwords, receipt content, or database credentials.

Before routing the hostname publicly, test from the VPS and through the real
hostname in a browser: TLS chain/hostname, login and logout, owner onboarding,
site/package/portal persistence after a fresh login, anonymous and
cross-tenant denial, session expiration/revocation, throttling, Magic Connect
UI/API denial, migration 033, database readiness failure behavior, and backup
restore into an isolated target. Capture redacted HTTP results and database
aggregate evidence only.

## Required owner inputs/approvals

- Confirmation that the owner controls `megamagic.tech`, the desired apex/`www`
  behavior, and willingness to point only the approved hostname at this VPS.
- Approval for the precise Caddy hostname block and reload, selected
  production workflow, production secrets creation, backup storage/retention,
  monitoring, and public traffic cutover.
- Acceptance criteria for the limited initial feature set and explicit approval
  to apply/test migration 033 in the next isolated release candidate.
- Explicit go/no-go after the new immutable artifact, isolated production
  deployment, HTTPS, recovery drill, and real public-hostname acceptance are
  evidenced. This document itself grants no deployment approval.

## Public-test deployment evidence — 2026-10-10

- Owner approval for this limited public test was received before VPS writes.
- Deployed artifact SHA-256:
  `4e78bae98d394fe40bcff6ce332282d212047247a21063c026b68ff0d4d79e93`.
- Isolated path/project: `/opt/mikromagic-build21-public-test-20261010` /
  `mikromagic-build21-public-test`.
- PostgreSQL migration revision `034`; database, API and web healthy; only the
  existing landing Caddy container publishes ports 80/443.
- `https://megamagic.tech/`, `/v1/health` and `/v1/ready` pass from the VPS and
  Mac. A real browser rendered the responsive sign-in page, reported the
  service available, enabled Sign in and emitted no warnings or errors.
- The first browser run exposed a development-demo button whose `/api` service
  is intentionally absent in production. Production builds now hide that
  control; the repaired build was redeployed and reverified.
- Targeted rollback:
  `/opt/mikromagic-public-test-rollback-20261010T0335Z`. No RouterOS, DNS,
  firewall, existing database, private RC or unrelated service was changed.

## Production redeploy evidence — 2026-10-10 17:13 UTC

- Owner decision: this VPS is production. Redeploy approved.
- Artifact: `4092ce1da282388f59ef1ef23e9ecb57adae45cccf85a26eb80ccb11f7ffeb1b`.
- Directory: `/opt/mikromagic-build21-public-test-20261010T171319Z`.
- Before the change:
  - pre-deploy `pg_dump` taken;
  - rollback tags `mikromagic-build21-public-test-{api,web,magic-hub,migrate}:rollback-20261010T171319Z`.
- Result:
  - migrations at `034`;
  - database, API, web and Hub healthy;
  - Hub published on `156.67.216.128:51820/udp` with an unchanged public key;
  - HTTPS 200; browser sign-in renders.
- Backup and recovery are now in place: nightly restore-verified dumps on the VPS, a daily off-VPS copy on the owner's Mac, and Keychain escrow of the Hub and backup keys.
- See `MIKROMAGIC-HOSTINGER-HANDOVER.md`.
