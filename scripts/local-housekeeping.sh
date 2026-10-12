#!/usr/bin/env bash
# Stop leftover local MikroMagic test processes and scratch files on this Mac.
# Safe scope: only this corrective checkout, known local ports, and /tmp mm-* scratch.
# Never touches VPS, Docker production stacks, Cursor itself, or unrelated apps.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS=(5173 8787 8788)
killed=0
removed=0

log() { printf '%s\n' "$*"; }

# Never touch Cursor, agent workers, or system helpers even if their argv mentions this repo.
is_protected_process() {
  local cmd=$1
  case "$cmd" in
    *Cursor.app*|*Cursor\ Helper*|*cursor-agent*|*agent-cli*|*cursor-agent-worker*|*Code\ Helper* )
      return 0
      ;;
  esac
  return 1
}

is_project_dev_process() {
  local cmd=$1 cwd=${2:-}
  if is_protected_process "$cmd"; then
    return 1
  fi
  case "$cmd" in
    *"$ROOT"/scripts/dev.mjs*|*"$ROOT"/node_modules/vite/bin/vite.js*|*"$ROOT"/server.py* )
      return 0
      ;;
    *scripts/dev.mjs*|*vite/bin/vite.js*|*uvicorn\ backend.app:create_app*|*uvicorn\ backend.app* )
      [[ "$cwd" == "$ROOT"* ]] && return 0
      [[ "$cmd" == *"$ROOT"* ]] && return 0
      return 1
      ;;
    *python*"$ROOT"*server.py*|*python3*server.py* )
      [[ "$cwd" == "$ROOT"* || "$cmd" == *"$ROOT"* ]] && return 0
      return 1
      ;;
  esac
  return 1
}

stop_pid() {
  local pid=$1 label=$2
  log "Stopping pid $pid — ${label:0:120}"
  kill -TERM "$pid" 2>/dev/null || true
  sleep 0.4
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  killed=$((killed + 1))
}

# Kill listeners on local dev ports only when the process clearly belongs to this project.
stop_project_listeners() {
  local port pid cmd cwd
  for port in "${PORTS[@]}"; do
    while read -r pid; do
      [[ -n "${pid:-}" ]] || continue
      cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
      cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1 || true)"
      if is_project_dev_process "$cmd" "$cwd"; then
        stop_pid "$pid" "$cmd"
      else
        log "Leaving pid $pid on :$port (not a project test server)"
      fi
    done < <(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
  done
}

# Catch orphaned children whose parent shell already exited (cwd may be gone).
stop_project_orphans() {
  local pid cmd
  while read -r pid cmd; do
    [[ -n "${pid:-}" ]] || continue
    if is_protected_process "$cmd"; then
      continue
    fi
    if is_project_dev_process "$cmd" ""; then
      stop_pid "$pid" "$cmd"
    fi
  done < <(ps -axo pid=,command= | grep -E 'scripts/dev\.mjs|vite/bin/vite\.js|uvicorn backend\.app|'"$ROOT"'/server\.py' | grep -v grep || true)
}

remove_scratch() {
  local path
  shopt -s nullglob
  for path in \
    /tmp/mm-*.sqlite3 \
    /tmp/mm-*.log \
    /tmp/mm-unit.log \
    /tmp/mm-full-tests.log \
    /tmp/suite-*.log \
    /tmp/deploy-*.log \
    /tmp/*walkthrough*.sqlite3 \
    /tmp/mm-deploy-*.lock
  do
    [[ -e "$path" ]] || continue
    # Only remove empty lock dirs or regular files we created for tests.
    if [[ -d "$path" ]]; then
      rmdir "$path" 2>/dev/null || true
    else
      rm -f "$path"
    fi
    removed=$((removed + 1))
    log "Removed $path"
  done
  shopt -u nullglob

  if [[ -d "$ROOT/.runtime" ]]; then
    find "$ROOT/.runtime" -maxdepth 1 -type f \( -name '*.sqlite3' -o -name '*.log' \) -print -delete 2>/dev/null \
      | while read -r path; do removed=$((removed + 1)); log "Removed $path"; done || true
  fi
}

main() {
  log "Housekeeping for $ROOT"
  stop_project_listeners
  stop_project_orphans
  remove_scratch
  log "Done. stopped_processes=$killed scratch_removed=$removed"
}

main "$@"
