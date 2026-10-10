# MikroMagic Build 21 deployment handoff

This package deploys the current web interface and FastAPI control plane with
PostgreSQL behind Caddy. It does **not** claim that RouterOS, WireGuard,
HotSpot/RADIUS, payment delivery, Jellyfin playback, backup execution, firmware
execution, or switch/AP telemetry is connected.

## Containers

- `web`: immutable React/Vite build served by Caddy; proxies `/v1/*` to `api`.
- `api`: FastAPI on the private network; never runs migrations during normal startup.
- `safe-change-worker`: private durable RouterOS recovery scheduler; polls protected changes and enforces their five-minute deadline.
- `db`: PostgreSQL 16 on the private network with a named persistent volume.

Only Caddy publishes host ports. PostgreSQL and FastAPI are not bound to the
VPS network interface.

## Login throttling and reverse-proxy identity

Login attempts are tracked in PostgreSQL by a normalized account key and a
source-IP key. Five failures for one account lock only that account for five
minutes. A separate source-IP spray guard allows 60 failed attempts in a
15-minute window before a 60-second cooldown; it is intentionally not the
five-attempt account lock. By default, the API uses the socket peer and ignores
forwarded-IP headers. Set `MIKROMAGIC_TRUSTED_PROXY_CIDRS` only to exact private
proxy IP addresses after verifying the API-side peer address; broad ranges are
rejected. Spoofed, malformed, or overlong `X-Forwarded-For` chains fall back to
the socket peer. Do not trust headers from an unverified proxy.

## Required operator gates

1. Audit this package and compare it to `V1-MASTER-REQUIREMENTS.md` and
   `LAUNCH-READINESS.md`.
2. Create `.env` from `.env.example`. Create `secrets/postgres_password.txt`
   and `secrets/backup_key.txt` with securely generated values. Set the secrets
   directory to mode `0700` and files to `0600`. Frozen v1 uses password-only
   authentication; do not provision an MFA key. Never commit or paste secrets.
3. Run `docker compose config` and an image build before starting services.
4. Run migrations as a controlled one-shot job and record the output:
   `docker compose --profile operations run --rm migrate`.
5. Start the initial acceptance environment with the loopback override:
   `docker compose -f compose.yaml -f compose.acceptance.yaml up -d db api web`.
   Do not change DNS or enable public TLS until separately approved.
6. Provision the first platform account interactively inside the API container:
   `docker compose exec api python -m backend.provision --username OWNER --role platform`
7. Verify `/v1/health`, sign-in, tenant isolation, migrations, restart behavior,
   volume persistence, and backup/restore before exposing production traffic.

## Honest acceptance state

Passing container health checks proves only that the web app, API, and database
started. It does not prove any live MikroTik or media integration. Use
`MIKROTIK-ACCEPTANCE-RUNBOOK.md` before changing the launch-readiness label.

The Compose file rotates container logs and caps CPU/memory use. Database/API
ports remain private. The acceptance override binds the web ports to loopback;
use an SSH tunnel for browser testing. Public port publication is a separate
operator decision.

Database backup encryption, off-host retention, restore drills, monitoring,
alerting, and immutable base-image digest pinning remain explicit production
acceptance gates; their absence must not be treated as completed work.

## RouterOS acceptance credentials

Read-only pre-flight credentials are operator-mounted from
`routeros-secrets/<router-id>.json`; they are never submitted by the web client
or stored in PostgreSQL. Each file contains `base_url`, `username`, `password`
and optionally `ca_bundle`, which must name a CA file in the same directory.
HTTPS with certificate verification is mandatory by default. HTTP can be
enabled only for an explicitly isolated lab with
`MIKROMAGIC_ROUTEROS_ALLOW_HTTP=true`; it is not a production setting.

The pre-flight reads RouterOS resource, RouterBOARD, WireGuard, HotSpot, DHCP
and NTP capability endpoints. Its result proves only that the read occurred; it
does not claim a WireGuard handshake, HotSpot enforcement or configuration
change. Router files and CA bundles must be mode `0600`, the directory `0700`,
and must never be committed, archived, pasted into chat or included in support
reports.

After an SME owner reviews the immutable Magic Hub router plan,
`POST /v1/routers/{router-id}/wireguard-evidence` reads the router's WireGuard
peers, matches the planned hub public key and interface, and stores durable,
tenant-scoped router-side evidence. `GET /v1/routers/{router-id}/evidence`
returns that history. A recent matching router-side handshake is not full
acceptance: hub-side peer state, tunnel management reachability, firewall
isolation and real packet flow still require separate acceptance evidence.

## Controlled RouterOS Safe Change and encrypted backups

Migration 027 introduces a fail-closed Safe Change record. The only supported
write in this checkpoint is the reviewed Magic Hub WireGuard peer's
`persistent-keepalive` value. Preview reads the actual peer and stores the
before/desired diff. Apply requires the SME Owner/Admin confirmation and the
exact preview revision. The adapter rereads the peer before writing; any stale
state becomes a whole-version configuration conflict.

Before the write, RouterOS must return a `show-sensitive=no` configuration
export. The API encrypts it with Fernet, writes the ciphertext to the private
`encrypted_backups` volume with mode `0600`, decrypts it and verifies its
SHA-256 checksum. Failure at any step blocks the RouterOS write. Create
`secrets/backup_key.txt` with a separately generated Fernet key and protect it
as mode `0600`. Never reuse the MFA key, commit either key, or place keys in
`.env`, logs, database records, chat, support bundles or source archives.

Safe-change backups expire after seven days and only the newest three per
router remain active; the fourth expires the oldest. SME APIs expose metadata,
not the internal storage reference or ciphertext. After apply, MikroMagic
rereads the exact peer. A mismatch attempts only a deterministic rollback of
that same field to the captured value. A confirmed match becomes `rolled_back`;
an unconfirmed rollback becomes `recovery_required`. Expected, desired and
actual sanitized states remain in change history for reconciliation.

Migration 028 and `safe-change-worker` add durable five-minute unreachable
handling. The visible lifecycle is Applying, Waiting for Gateway, then
Reconnected only after a matching reread, or Failed/Recovery Required. At the
deadline the worker attempts rollback only for the supported deterministic
keepalive change. It never reports recovery without verifying actual RouterOS
state. Repeated scheduler passes and process restarts are revision-fenced and
idempotent.

Whole-version configuration conflicts expose exactly two choices. Keep Router
Version rereads the router and adopts that verified state without an unnecessary
backup. Keep MikroMagic Version requires Owner confirmation and a newly verified
encrypted safety backup before apply. There is no per-setting merge. Resolved
conflict evidence remains view-only for one week.

This workflow is simulated/test verified only. RouterOS REST export/write
semantics, filesystem durability, actual disconnect/reconnect behavior,
five-minute timeout and rollback must be exercised on the disposable
MikroTik/Magic Hub environment before the feature can move from 🟡 to accepted.
Full-device restore and firmware-triggered backups are not claimed.

Docker was unavailable in the checkpoint workspace. Therefore base/acceptance
Compose rendering, image build, worker startup/restart, PostgreSQL concurrency,
volume persistence and loopback port binding remain pending on the prepared VPS;
YAML inspection is not an acceptance result.
