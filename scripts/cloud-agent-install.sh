#!/usr/bin/env bash
# Cursor cloud agent install step (see .cursor/environment.json). Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
npm ci
