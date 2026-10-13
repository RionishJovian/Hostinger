#!/usr/bin/env bash
# VPS side of scripts/deploy-hostinger-public-test.sh; uploaded into the new release directory
# and run with stdin closed. Prints key=value lines that the local script verifies.
set -euo pipefail
TS=$1 SHA=$2 ALLOW_INFRA=$3
P=mikromagic-build21-public-test
NEW=/opt/$P-$TS
DB=$P-db-1
stop() { echo "STOP: $*" >&2; exit 1; }
note() { echo "-- $*" >&2; }
health() { docker inspect -f '{{.State.Health.Status}}' "$P-$1-1" 2>/dev/null || echo missing; }
alembic_now() { docker exec $DB psql -U build21_public_test -d build21_public_test -Atc 'select version_num from alembic_version'; }

PREV=$(docker inspect $P-api-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')
[[ $PREV == /opt/$P-20* ]] || stop "unexpected running release directory: $PREV"
for s in db api web magic-hub; do [ "$(health $s)" = healthy ] || stop "$s is $(health $s) before deploy"; done

note "previous release $PREV"
cd "$NEW"
echo "$SHA  mikromagic-build21-public-test.zip" | sha256sum -c --quiet - || stop "artifact checksum mismatch"
echo "$SHA" > RELEASE_SHA256
python3 -c 'import zipfile; zipfile.ZipFile("mikromagic-build21-public-test.zip").extractall(".")'
chmod 755 docker/api-entrypoint.sh
cp -a "$PREV/.env" "$PREV/secrets" .
install -d -m 700 backups

changed=""
for f in compose.hostinger-public-test.yaml Dockerfile.api Dockerfile.web Dockerfile.hub docker/Caddyfile \
         requirements.hub.txt backend/__init__.py backend/hub_agent.py; do
  cmp -s "$f" "$PREV/$f" || changed="$changed $f"
done
[ -z "$changed" ] || [ "$ALLOW_INFRA" = 1 ] || stop "infrastructure or Hub files changed:$changed (review, then rerun with ALLOW_INFRA_CHANGE=1)"

note "database dump"
pre=$(alembic_now)
echo "$pre" > backups/pre-deploy.alembic
docker exec $DB pg_dump -U build21_public_test -d build21_public_test -Fc > backups/pre-deploy.dump
chmod 600 backups/pre-deploy.dump
sha256sum backups/pre-deploy.dump > backups/pre-deploy.dump.sha256
entries=$(docker exec -i $DB pg_restore -l < backups/pre-deploy.dump | grep -vc '^;' || true)
[ "${entries:-0}" -gt 0 ] || stop "pre-deploy dump is empty"

for s in api web magic-hub; do docker tag "$(docker inspect -f '{{.Image}}' "$P-$s-1")" "$P-$s:rollback-$TS"; done
if docker inspect "$P-safe-change-worker-1" >/dev/null 2>&1; then
  docker tag "$(docker inspect -f '{{.Image}}' "$P-safe-change-worker-1")" "$P-safe-change-worker:rollback-$TS"
fi
docker tag "$P-migrate:latest" "$P-migrate:rollback-$TS"
note "image build"
C="docker compose -p $P -f compose.hostinger-public-test.yaml"
$C --profile operations build > backups/build.log 2>&1 || stop "image build failed (see $NEW/backups/build.log); nothing was restarted"

target=$(docker run --rm -e DATABASE_URL=sqlite:// "$P-migrate:latest" python -m alembic heads | awk '{print $1}')
rehearsal=skipped
if [ "$target" != "$pre" ]; then
  note "PostgreSQL rehearsal $pre -> $target"
  net=mm-rehearsal-$TS rdb=mm-rehearsal-db-$TS
  cleanup() { docker rm -f "$rdb" >/dev/null 2>&1 || true; docker network rm "$net" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  docker network create --internal "$net" >/dev/null
  docker run -d --name "$rdb" --network "$net" -e POSTGRES_USER=rehearsal -e POSTGRES_PASSWORD=rehearsal \
    -e POSTGRES_DB=rehearsal postgres:17-alpine >/dev/null
  for _ in $(seq 60); do docker exec "$rdb" pg_isready -h 127.0.0.1 -U rehearsal -d rehearsal >/dev/null 2>&1 && break; sleep 1; done
  docker exec -i "$rdb" pg_restore --no-owner --no-privileges -U rehearsal -d rehearsal < backups/pre-deploy.dump \
    || stop "rehearsal restore failed; nothing was migrated or restarted"
  R="docker run --rm --network $net -e DATABASE_URL=postgresql+psycopg://rehearsal:rehearsal@$rdb:5432/rehearsal $P-migrate:latest python -m alembic"
  { $R upgrade head && $R downgrade "$pre" && $R upgrade head; } > backups/rehearsal.log 2>&1 \
    || stop "PostgreSQL rehearsal $pre -> $target failed (see $NEW/backups/rehearsal.log); nothing was migrated or restarted"
  cleanup; trap - EXIT
  rehearsal="$pre -> $target -> $pre -> $target clean"
fi

note "migrate and start"
$C --profile operations run --rm -T migrate < /dev/null > backups/migrate.log 2>&1 \
  || stop "migration failed (see $NEW/backups/migrate.log); restore backups/pre-deploy.dump before restarting old images"
recreate="api web safe-change-worker"
case "$changed" in *hub*|*backend/__init__.py*) recreate="$recreate magic-hub" ;; esac
{ $C up -d && $C up -d --no-deps --force-recreate $recreate; } > backups/up.log 2>&1 \
  || stop "compose up failed (see $NEW/backups/up.log)"

ok=0
for _ in $(seq 60); do
  ok=1; for s in db api web magic-hub; do [ "$(health $s)" = healthy ] || ok=0; done
  [ $ok = 1 ] && break; sleep 3
done
[ $ok = 1 ] || stop "containers not healthy after 3 minutes"
for s in $recreate; do
  [ "$(docker inspect -f '{{.Image}}' "$P-$s-1")" = "$(docker image inspect -f '{{.Id}}' "$P-$s:latest")" ] \
    || stop "$s is not running the newly built image"
done
# Worker has healthcheck disabled (not an HTTP server); require running + stable, clean recent logs.
[ "$(docker inspect -f '{{.State.Status}}' "$P-safe-change-worker-1")" = running ] \
  || stop "safe-change-worker is not running"
sleep 12
[ "$(docker inspect -f '{{.State.Status}}' "$P-safe-change-worker-1")" = running ] \
  || stop "safe-change-worker left the running state"
restarts=$(docker inspect -f '{{.RestartCount}}' "$P-safe-change-worker-1")
[ "${restarts:-0}" -eq 0 ] || stop "safe-change-worker restarted ${restarts} times"
docker logs --tail 50 "$P-safe-change-worker-1" > backups/safe-change-worker.log 2>&1 || true
grep -qiE 'traceback|scheduler pass failed|error' backups/safe-change-worker.log \
  && stop "safe-change-worker logs show errors (see $NEW/backups/safe-change-worker.log)" || true
# Empty or quiet logs are OK: the poller is silent when there is no due work.

echo "previous=$PREV"
echo "new=$NEW"
echo "alembic=$pre -> $(alembic_now)"
echo "dump_entries=$entries"
echo "rehearsal=$rehearsal"
echo "infra_changed=${changed:- none}"
echo "recreated=$recreate"
echo "safe_change_worker=running"
echo "hub_key=$(docker exec $P-magic-hub-1 wg show mm-prod-hub public-key)"
echo "hub_port=$(docker port $P-magic-hub-1 51820/udp | head -1)"
