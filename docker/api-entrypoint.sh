#!/bin/sh
set -eu

if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then
  POSTGRES_PASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
  export POSTGRES_PASSWORD
fi
if [ -n "${MIKROMAGIC_BACKUP_KEY_FILE:-}" ]; then
  MIKROMAGIC_BACKUP_KEY="$(cat "$MIKROMAGIC_BACKUP_KEY_FILE")"
  export MIKROMAGIC_BACKUP_KEY
fi
if [ -z "${DATABASE_URL:-}" ]; then
  DATABASE_URL="$(python -c 'import os,urllib.parse; print("postgresql+psycopg://%s:%s@%s:5432/%s" % tuple(urllib.parse.quote(os.environ[k], safe="") for k in ("POSTGRES_USER","POSTGRES_PASSWORD","POSTGRES_HOST","POSTGRES_DB")))')"
  export DATABASE_URL
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec python -m uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8788 --workers "${MIKROMAGIC_API_WORKERS:-2}"
