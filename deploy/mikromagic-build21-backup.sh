#!/bin/bash
# Nightly MikroMagic Build 21 production backup with isolated restore verification.
# Backs up only the public-test project's PostgreSQL database and Hub peer state.
# A dump replaces older copies only after it restores into a throwaway database.
set -euo pipefail

PROJECT=mikromagic-build21-public-test
DB_CONTAINER=$PROJECT-db-1
HUB_CONTAINER=$PROJECT-magic-hub-1
DB_NAME=build21_public_test
OUT=/var/backups/mikromagic-build21
KEEP=7
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
VERIFY=mikromagic-build21-backup-verify-$STAMP

umask 077
install -d -m 0700 "$OUT"
TMP=$(mktemp -d)
trap 'docker rm -f "$VERIFY" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
say(){ echo "[$(date -u +%FT%TZ)] $*"; }

say "backup start $STAMP"
live_tables=$(docker exec "$DB_CONTAINER" psql -U "$DB_NAME" -d "$DB_NAME" -tAc "select count(*) from information_schema.tables where table_schema='public'")
live_head=$(docker exec "$DB_CONTAINER" psql -U "$DB_NAME" -d "$DB_NAME" -tAc "select version_num from alembic_version")
[ "${live_tables:-0}" -gt 0 ] || { say "FATAL: cannot read live database"; exit 1; }

docker exec "$DB_CONTAINER" pg_dump -U "$DB_NAME" -d "$DB_NAME" --format=custom --no-owner --no-acl > "$TMP/db.dump"
[ -s "$TMP/db.dump" ] || { say "FATAL: empty dump"; exit 1; }

image=$(docker inspect --format '{{.Config.Image}}' "$DB_CONTAINER")
docker run -d --name "$VERIFY" --network none -e POSTGRES_USER=verify -e POSTGRES_DB=verify -e POSTGRES_HOST_AUTH_METHOD=trust "$image" >/dev/null
for _ in $(seq 1 60); do docker exec "$VERIFY" pg_isready -U verify -d verify >/dev/null 2>&1 && break; sleep 1; done
docker exec -i "$VERIFY" pg_restore -U verify -d verify --no-owner --no-acl --exit-on-error < "$TMP/db.dump"
restored_tables=$(docker exec "$VERIFY" psql -U verify -d verify -tAc "select count(*) from information_schema.tables where table_schema='public'")
restored_head=$(docker exec "$VERIFY" psql -U verify -d verify -tAc "select version_num from alembic_version")
if [ "$restored_tables" != "$live_tables" ] || [ "$restored_head" != "$live_head" ]; then
  say "VERIFY FAILED: tables $restored_tables/$live_tables head $restored_head/$live_head; older backups kept"
  exit 1
fi

if docker cp "$HUB_CONTAINER:/var/lib/mikromagic-hub/." "$TMP/hub_state" 2>/dev/null; then
  tar -C "$TMP" -czf "$TMP/hub_state.tgz" hub_state
fi

cp "$TMP/db.dump" "$OUT/db_$STAMP.dump"
[ -f "$TMP/hub_state.tgz" ] && cp "$TMP/hub_state.tgz" "$OUT/hub_state_$STAMP.tgz"
(cd "$OUT" && sha256sum "db_$STAMP.dump" $( [ -f "hub_state_$STAMP.tgz" ] && echo "hub_state_$STAMP.tgz") > "SHA256SUMS_$STAMP")
chmod 0600 "$OUT"/*
for prefix in db_ hub_state_ SHA256SUMS_; do
  ls -1t "$OUT"/$prefix* 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
done
say "backup verified: tables=$live_tables head=$live_head size=$(stat -c%s "$OUT/db_$STAMP.dump")"
