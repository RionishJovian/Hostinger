#!/usr/bin/env bash
# Cursor cloud agent install step (see .cursor/environment.json). Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf .venv
  if ! python3 -m venv .venv >/dev/null 2>&1; then
    rm -rf .venv
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv
    python3 -m venv .venv
  fi
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
npm ci
