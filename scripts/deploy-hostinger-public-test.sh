#!/usr/bin/env bash
# Deploy the committed source to the megamagic.tech public test on the Hostinger VPS.
# Runs from the owner's Mac or a Cursor cloud agent; needs the `mikromagic-hostinger` SSH alias.
# Stops on the first anomaly. Never touches other stacks, /opt/build21, /opt/mikromagic-v8 or routers.
#
#   scripts/deploy-hostinger-public-test.sh
#   ALLOW_INFRA_CHANGE=1 scripts/deploy-hostinger-public-test.sh   # only after reviewing a reported
#                                                                  # Compose/Dockerfile/Caddy/Hub change
set -euo pipefail
cd "$(dirname "$0")/.."

HOST=${MIKROMAGIC_SSH_HOST:-mikromagic-hostinger}
PROJECT=mikromagic-build21-public-test
HUB_KEY=TG1jLN13+hA1Eg9/1h0DykQ768ZHZO54WFGAZWhjL0o=
HUB_PORT=156.67.216.128:51820
PY=${PYTHON:-.venv/bin/python}
ZIP=release/mikromagic-build21-public-test.zip
stop() { echo "STOP: $*" >&2; exit 1; }

[ -z "$(git status --porcelain)" ] || stop "working tree has uncommitted changes"
git fetch -q origin main
git merge-base --is-ancestor HEAD origin/main || stop "deploy only commits already pushed to origin/main"
commit=$(git rev-parse --short HEAD)

echo "== Local checks for $commit"
"$PY" -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
npm run build
npm run test:sites
node scripts/generate-source-manifest.mjs >/dev/null
[ -z "$(git status --porcelain)" ] || stop "source manifest is out of date; commit .corrective-source-manifest.txt and rerun"
bundle=$(cd dist/client/assets && ls index-*.js)
artifact=$("$PY" scripts/package-hostinger-public-test.py)
sha=$(printf '%s\n' "$artifact" | sed -n 's/^sha256=//p')
files=$(printf '%s\n' "$artifact" | sed -n 's/^files=//p')
[ -n "$sha" ] || stop "packaging did not report a sha256"

TS=$(date -u +%Y%m%dT%H%M%SZ)
NEW=/opt/$PROJECT-$TS
echo "== Upload $sha ($files files) to $NEW"
ssh "$HOST" "test ! -e $NEW && install -d -m 700 $NEW" || stop "cannot create $NEW"
scp -q "$ZIP" "$HOST:$NEW/"

echo "== Deploy on the VPS"
summary=$(ssh "$HOST" "bash -s -- $TS $sha ${ALLOW_INFRA_CHANGE:-0}" <<'REMOTE'
set -euo pipefail
TS=$1 SHA=$2 ALLOW_INFRA=$3
P=mikromagic-build21-public-test
NEW=/opt/$P-$TS
DB=$P-db-1
stop() { echo "STOP: $*" >&2; exit 1; }
health() { docker inspect -f '{{.State.Health.Status}}' "$P-$1-1" 2>/dev/null || echo missing; }
alembic_now() { docker exec $DB psql -U build21_public_test -d build21_public_test -Atc 'select version_num from alembic_version'; }

PREV=$(docker inspect $P-api-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')
[[ $PREV == /opt/$P-20* ]] || stop "unexpected running release directory: $PREV"
for s in db api web magic-hub; do [ "$(health $s)" = healthy ] || stop "$s is $(health $s) before deploy"; done

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

pre=$(alembic_now)
echo "$pre" > backups/pre-deploy.alembic
docker exec $DB pg_dump -U build21_public_test -d build21_public_test -Fc > backups/pre-deploy.dump
chmod 600 backups/pre-deploy.dump
sha256sum backups/pre-deploy.dump > backups/pre-deploy.dump.sha256
entries=$(docker exec -i $DB pg_restore -l < backups/pre-deploy.dump | grep -vc '^;' || true)
[ "${entries:-0}" -gt 0 ] || stop "pre-deploy dump is empty"

for s in api web magic-hub migrate; do docker tag "$P-$s:latest" "$P-$s:rollback-$TS"; done
C="docker compose -p $P -f compose.hostinger-public-test.yaml"
$C --profile operations build > backups/build.log 2>&1 || stop "image build failed (see $NEW/backups/build.log); nothing was restarted"

target=$(docker run --rm -e DATABASE_URL=sqlite:// "$P-migrate:latest" python -m alembic heads | awk '{print $1}')
rehearsal=skipped
if [ "$target" != "$pre" ]; then
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

$C --profile operations run --rm migrate > backups/migrate.log 2>&1 \
  || stop "migration failed (see $NEW/backups/migrate.log); restore backups/pre-deploy.dump before restarting old images"
$C up -d > backups/up.log 2>&1 || stop "compose up failed (see $NEW/backups/up.log)"

ok=0
for _ in $(seq 60); do
  ok=1; for s in db api web magic-hub; do [ "$(health $s)" = healthy ] || ok=0; done
  [ $ok = 1 ] && break; sleep 3
done
[ $ok = 1 ] || stop "containers not healthy after 3 minutes"

echo "previous=$PREV"
echo "new=$NEW"
echo "alembic=$pre -> $(alembic_now)"
echo "dump_entries=$entries"
echo "rehearsal=$rehearsal"
echo "infra_changed=${changed:- none}"
echo "hub_key=$(docker exec $P-magic-hub-1 wg show mm-prod-hub public-key)"
echo "hub_port=$(docker port $P-magic-hub-1 51820/udp | head -1)"
REMOTE
) || stop "remote deploy stopped; see the message above"
printf '%s\n' "$summary"

echo "== Public checks"
value() { printf '%s\n' "$summary" | sed -n "s/^$1=//p"; }
[ "$(value hub_key)" = "$HUB_KEY" ] || stop "Hub public key changed"
[ "$(value hub_port)" = "$HUB_PORT" ] || stop "Hub UDP port not published as $HUB_PORT"
for url in https://megamagic.tech/ https://www.megamagic.tech/ https://megamagic.tech/v1/ready; do
  code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$url")
  [ "$code" = 200 ] || stop "$url returned $code"
done
served=$(curl -s -m 20 https://megamagic.tech/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
[ "$served" = "assets/$bundle" ] || stop "served bundle $served differs from local $bundle"

previous=$(value previous)
cat <<EOF
== Deployed $commit at $TS
artifact sha256 $sha ($files files), bundle $bundle
Rollback: on the VPS, for s in api web magic-hub migrate; do docker tag $PROJECT-\$s:rollback-$TS $PROJECT-\$s:latest; done
          then cd $previous && docker compose -p $PROJECT -f compose.hostinger-public-test.yaml up -d
          Restore $NEW/backups/pre-deploy.dump only if the migration itself is at fault.
Next: record this in MIKROMAGIC-HOSTINGER-HANDOVER.md and append a Notion execution checkpoint.
EOF
