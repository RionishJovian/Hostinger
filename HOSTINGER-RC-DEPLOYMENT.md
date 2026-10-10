# Build 21 private Hostinger release candidate

This record documents the approved deployment to
`srv2032937.hstgr.cloud` (`156.67.216.128`). The command sequence is retained
for reproducibility. Never run it against any v8 acceptance stack or the
Hermes-affected stack.

## Identity and boundaries

- Source: this corrective Build 21 directory; artifact:
  `release/mikromagic-build21-hostinger-rc.zip`. Verify its SHA-256 against the
  value reported with the proposal before copying or extracting it:
  `2b763be4426726d0ea79a5f6cf2992f46c721d7c42844431d958f063327f3ed4`.
- New target directory: `/opt/mikromagic-build21-rc` (absent at preflight).
- Compose project: `mikromagic-build21-rc`; containers: `db`, `migrate`
  (one-shot), `api`, `web`. No RouterOS safe-change worker is started.
- Named volumes: `mikromagic-build21-rc_postgres_data` and
  `mikromagic-build21-rc_encrypted_backups`. Networks:
  `mikromagic-build21-rc_private` (internal DB network) and
  `mikromagic-build21-rc_frontend` (API/web only).
- PostgreSQL 17 private container: DB and role `build21_rc`; no published DB
  port. API port 8788 is container-only. Web is bound *only* to VPS loopback
  `127.0.0.1:18081`, with no TLS/domain/public Caddy change.
- `MIKROMAGIC_ENVIRONMENT=hostinger-private-rc`,
  `MIKROMAGIC_MAGIC_CONNECT_TEST_MODE=false`, no RouterOS credentials mounted,
  and no worker: pairing and live RouterOS work stay unavailable. Never claim
  Connected from this release-candidate test.
- Host-side secret directory is `0700`; `postgres_password.txt` and
  `backup_key.txt` are distinct, new, owned by the RC container identity
  `100:101`, mode `0400`, and outside the ZIP. Only RC containers mount them.
  No existing database, volume, credential, network or container is reused.

## Deployment sequence

1. Recheck target identity, free disk/RAM, port 18081, and absence of the new
   path/project/volume/network names. Abort on any collision. Recheck artifact
   SHA-256 on both ends and validate every archive path before extraction.
   Copy only the ZIP to a new directory under `/opt/mikromagic-build21-rc`;
   extraction must not overwrite any file. Restrict the directory to the
   deployment operator. Once the collision gate passes, use:

   ```sh
   ssh mikromagic-mac 'install -d -m 0700 /opt/mikromagic-build21-rc'
   scp release/mikromagic-build21-hostinger-rc.zip mikromagic-mac:/opt/mikromagic-build21-rc/
   ssh mikromagic-mac 'cd /opt/mikromagic-build21-rc && sha256sum mikromagic-build21-hostinger-rc.zip && python3 -c '\''import pathlib,zipfile; root=pathlib.Path(".").resolve(); z=zipfile.ZipFile("mikromagic-build21-hostinger-rc.zip"); names=z.namelist(); assert names and all(not pathlib.PurePosixPath(n).is_absolute() and ".." not in pathlib.PurePosixPath(n).parts for n in names); assert all(not (root/pathlib.PurePosixPath(n)).exists() for n in names); [z.extract(n,root) for n in names]; print("archive_paths_validated",len(names))'\'''
   ```
2. In that directory, create `secrets/` mode `0700`. Generate a unique
   48-byte URL-safe random PostgreSQL password into
   `secrets/postgres_password.txt` and an independent 32-byte URL-safe
   base64 Fernet key into `secrets/backup_key.txt`.
   Generate directly to files without command tracing, shell history output,
   logs, copy/paste or displaying the values. Do not create a `.env` file.
   Run inside the newly extracted RC directory, with shell tracing disabled:

   ```sh
   install -d -m 0700 secrets
   umask 077
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > secrets/postgres_password.txt
   python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())' > secrets/backup_key.txt
   chown 100:101 secrets/postgres_password.txt secrets/backup_key.txt
   chmod 0400 secrets/postgres_password.txt secrets/backup_key.txt
   stat -c '%u:%g %a %n' secrets secrets/postgres_password.txt secrets/backup_key.txt
   ```
3. Run `docker compose -f compose.hostinger-rc.yaml config --quiet`, then
   `docker compose -f compose.hostinger-rc.yaml build api web migrate`.
   Inspect image contents for excluded docs and runtime files before startup.
   Abort on failure; do not alter or prune existing Docker images/cache.
4. Start only the new database:
   `docker compose -f compose.hostinger-rc.yaml up -d db`.
   Run migrations as a one-shot job:
   `docker compose -f compose.hostinger-rc.yaml --profile operations run --rm migrate`.
   Verify exactly one Alembic head, `032`, via `alembic current` inside the
   migration image and `select version_num from alembic_version` in the new
   database. Abort if either disagrees. Never migrate an existing database.
5. Start only `api` and `web` from this Compose project. Wait for all three
   persistent containers to be healthy. Provision one *synthetic* platform
   account interactively using
   `docker compose -f compose.hostinger-rc.yaml exec api python -m backend.provision --username RC_OPERATOR --role platform`.
   Enter a new credential at the prompt; never print it or store it in the
   artifact. Do not provision production/customer accounts.
6. Open a local-only tunnel from the owner's Mac:
   `ssh -N -L 18081:127.0.0.1:18081 mikromagic-mac`.
   Browser origin: `http://127.0.0.1:18081/`. Do not bind a public address or
   enable a domain, external firewall rule or public Caddy route.

## Post-deployment acceptance

- `curl -fsS http://127.0.0.1:18081/v1/health` over the SSH tunnel must return
  service `mikromagic` with `network_adapter: not_connected`; `/` must serve
  the Build 21 UI. Record container health and image IDs/digests.
- Use real Chrome through the tunnel with the synthetic platform login. Create
  two synthetic businesses/owners, sites, one package and a portal draft;
  refresh and re-login; read back unchanged values. Record actual HTTP status
  codes (successful login/write/read, anonymous 401, cross-tenant 404).
- In the new database only, verify the Alembic row is `032` and count those
  exact synthetic records by their run-specific names/IDs. Never inspect any
  pre-existing database or customer row. Confirm a read after web/API restart
  still sees the same records; restart only this new project after approval.
- Owner UI and technician UI must say Magic Connect pairing is unavailable;
  pairing controls must be absent. `GET /v1/magic-connect/capability` must
  report `pairing_available=false`; attempted creation/claim must return 503;
  the new DB must contain zero public pairing attempts. No RouterOS connection
  or Connected claim is part of this acceptance.
- Confirm `docker ps` shows only `127.0.0.1:18081->80/tcp` for the RC web,
  and no published RC API/DB ports. Check existing acceptance stacks remain
  running with the same container IDs and volume names as pre-deploy.

## Backup and targeted rollback

- Before any *later* RC schema or image upgrade, stop only RC `api` and `web`,
  then run `pg_dump --format=custom --no-owner --no-acl` as `build21_rc`
  inside the RC `db` container. Redirect stdout directly to a dated file in
  `/opt/mikromagic-build21-rc/backups/` with host directory `0700` and file
  `0600`; never print the dump or copy it into the ZIP. Record SHA-256 and
  `pg_restore --list` success. Resume only RC services after the backup. Exact
  command pattern, with a manually selected unique timestamp:

  ```sh
  cd /opt/mikromagic-build21-rc
  install -d -m 0700 backups
  docker compose -f compose.hostinger-rc.yaml stop api web
  umask 077
  docker compose -f compose.hostinger-rc.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' > backups/pre-upgrade-YYYYMMDDTHHMMSSZ.dump
  sha256sum backups/pre-upgrade-YYYYMMDDTHHMMSSZ.dump
  docker compose -f compose.hostinger-rc.yaml exec -T db pg_restore --list < backups/pre-upgrade-YYYYMMDDTHHMMSSZ.dump
  ```
- For this *first* candidate deployment, no older RC state exists. If a gate
  fails, capture logs/evidence, then run `docker compose -f
  compose.hostinger-rc.yaml down` from the RC directory. This stops/removes
  only RC containers/networks; **omit `-v`** so RC database and backup volumes
  remain recoverable. Do not prune images or alter any v8/Hermes resources.
- For a later RC upgrade rollback, stop only RC `api`/`web`, restore the prior
  known-good artifact/images, and run `pg_restore --clean --if-exists` from its
  verified custom-format dump into **only** `build21_rc` while clients are
  stopped. Check Alembic head, health, synthetic login/isolation/persistence,
  then restart only RC `api`/`web`. Never restore into an existing v8 database.
  The restore command is:

  ```sh
  cd /opt/mikromagic-build21-rc
  docker compose -f compose.hostinger-rc.yaml stop api web
  sha256sum backups/pre-upgrade-YYYYMMDDTHHMMSSZ.dump
  docker compose -f compose.hostinger-rc.yaml exec -T db pg_restore -U build21_rc -d build21_rc --clean --if-exists --no-owner --no-acl --exit-on-error --single-transaction < backups/pre-upgrade-YYYYMMDDTHHMMSSZ.dump
  ```
- A Hostinger whole-VPS snapshot is *not* the routine rollback: restoring it
  would also roll back unrelated stacks. A targeted RC dump/artifact is the
  primary plan. An off-VPS encrypted copy and restore drill are separate
  prerequisites before any public/customer deployment.
