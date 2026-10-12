#!/usr/bin/env bash
# Full local checks: Python tests in parallel, frontend build, Node tests.
# On success with a clean committed tree, records that tree as passed so
# scripts/deploy-hostinger-public-test.sh does not run the same checks again.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}

"$PY" scripts/run-tests.py
npm run build
node --test tests/*.test.mjs
node scripts/generate-source-manifest.mjs >/dev/null

if git status --porcelain | grep -qx ' M .corrective-source-manifest.txt' && [ "$(git status --porcelain | wc -l)" -eq 1 ]; then
  echo "Checks passed, but .corrective-source-manifest.txt changed (the test package was rebuilt); commit it and rerun to record the pass"
elif [ -z "$(git status --porcelain)" ]; then
  git rev-parse 'HEAD^{tree}' > "$(git rev-parse --git-dir)/mikromagic-checks-passed"
  echo "Checks passed for tree $(git rev-parse --short 'HEAD^{tree}') (commit $(git rev-parse --short HEAD))"
else
  echo "Checks passed; uncommitted changes, so no deploy record was written"
fi
