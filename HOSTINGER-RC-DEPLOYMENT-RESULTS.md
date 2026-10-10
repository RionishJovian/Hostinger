# Build 21 private Hostinger RC — actual results

Run date: 2026-10-09. Scope: approved private RC deployment only. This is not a
public launch or full Magic Connect acceptance.

## Deployment

- Approved artifact SHA-256 matched locally and on `srv2032937.hstgr.cloud`:
  `2b763be4426726d0ea79a5f6cf2992f46c721d7c42844431d958f063327f3ed4`.
- Target `/opt/mikromagic-build21-rc`; Compose project
  `mikromagic-build21-rc`.
- Containers `mikromagic-build21-rc-db-1`, `mikromagic-build21-rc-api-1`, and
  `mikromagic-build21-rc-web-1` are healthy. The one-shot migration container
  was removed by Compose after completion. No safe-change worker exists.
- PostgreSQL database and role: `build21_rc`; verification database:
  `build21_rc_restorecheck`.
- New volumes: `mikromagic-build21-rc_postgres_data` and
  `mikromagic-build21-rc_encrypted_backups`. New private networks:
  `mikromagic-build21-rc_private` and `mikromagic-build21-rc_frontend`.
- Web binding verified as `127.0.0.1:18081->80/tcp`. API 8788 and database
  5432 have no host bindings. Access succeeded through an authenticated SSH
  tunnel at `http://127.0.0.1:18081/`.
- New PostgreSQL password and backup key were generated for this RC only.
  Their directory is mode `0700`; files are mode `0400`, owned by the RC
  container UID/GID `100:101`. Values were never displayed.
- Initial migration invocation stopped before applying schema because
  file-backed secrets were unreadable by the image's non-root UID. The two RC
  secret files were restricted to that UID; secret access then passed and
  migration completed. No app authentication or authorization was weakened.

## Acceptance

- Migration: database and source each report exactly one head, `032`.
- Real Google Chrome browser acceptance through the SSH tunnel: PASS. Platform
  login; two business/owner onboarding flows; forced owner password changes;
  site and package creation/readback; portal draft update/readback; refresh and
  logout/re-login persistence all passed.
- Authentication and isolation: PASS. Anonymous request returned 401; both
  cross-tenant read and write returned 404. Owner and technician UI hid pairing
  controls. Capability read reported unavailable; create and claim returned
  503. PostgreSQL had zero Magic Connect attempts and enrollments.
- Explicit UI logout/re-login check: PASS. Sign-out returned 200, the old token
  then returned 401, re-login returned 200, and both synthetic businesses were
  visible after re-login. Evidence:
  `/private/tmp/mm-build21-rc.yZMF7N/logout-relogin-result.json`.
- Browser-run PostgreSQL evidence: 2 synthetic tenants, 2 sites, 1 package, 1
  updated portal draft, migration `032`; 0 public pairing attempts.
- Evidence (local, synthetic only):
  `/private/tmp/mm-build21-rc.yZMF7N/browser-result.json`,
  `magic-connect-unavailable.png`, `technician-pairing-unavailable.png`, and
  `owner-records-after-relogin.png`. The synthetic platform login is in the
  mode-0600 local file `login.json` in that directory; it is not in the ZIP.

## Backup and preservation

- RC-only custom PostgreSQL backup:
  `/opt/mikromagic-build21-rc/backups/acceptance-20261009.dump`, mode `0600`,
  size 148,256 bytes, SHA-256
  `37744efb22002a3def00257bc8352d91f0aa5f6e8da8893b2031d7b544fbd81e`.
- `pg_restore --list` passed. Restore into the separate
  `build21_rc_restorecheck` database passed. Migration, tenants, users, sites,
  packages, portal settings, audit-event, pairing-attempt and enrollment counts
  matched source and restored databases (`032, 2, 3, 2, 1, 2, 14, 0, 0`). The
  verification database and backup are retained.
- All four pre-existing MikroMagic stacks and the public landing container
  remained present and running; the existing application containers reported
  healthy. Their prior long uptimes continued, and their PostgreSQL volume
  mounts remained attached under their original names. The Hermes-affected
  web container remained healthy. No existing stack, database volume, Caddy,
  DNS, or public listener was changed.
- Post-build VPS capacity: 182 GB free disk. Docker reports 5.502 GB images,
  417.4 MB volumes, and 5.261 GB build cache. No image, container, volume or
  cache pruning was run.

The private RC acceptance passed. Public deployment, production readiness,
RouterOS enrollment, and Magic Connect Connected remain unverified.
