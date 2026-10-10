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
scp -q scripts/deploy-hostinger-remote.sh "$HOST:$NEW/deploy-remote.sh"

echo "== Deploy on the VPS"
summary=$(ssh "$HOST" "bash $NEW/deploy-remote.sh $TS $sha ${ALLOW_INFRA_CHANGE:-0}" </dev/null) \
  || stop "remote deploy stopped; see the message above"
printf '%s\n' "$summary"
printf '%s\n' "$summary" | grep -q '^hub_port=' || stop "remote deploy ended without a complete summary"

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
          then cd $previous && docker compose -p $PROJECT -f compose.hostinger-public-test.yaml up -d --no-deps --force-recreate $(value recreated)
          Restore $NEW/backups/pre-deploy.dump only if the migration itself is at fault.
Next: record this in MIKROMAGIC-HOSTINGER-HANDOVER.md and append a Notion execution checkpoint.
EOF
