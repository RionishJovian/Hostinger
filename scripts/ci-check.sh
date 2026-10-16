#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}

cd "$ROOT"
PYTHONPATH=. "$PYTHON" -m unittest discover -s tests -p 'test_*.py'
npm ci --prefix owner-web
npm run build --prefix owner-web
