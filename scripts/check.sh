#!/usr/bin/env bash
# Full local checks: Python tests in parallel, frontend build, Node tests.
# On success, records the passed source tree (and commit) so deploy can skip
# repeating checks for the same tree or for docs-only follow-up commits.
set -euo pipefail

checks_pass_lib() {
  checks_pass_stamp_file() {
    echo "$(git rev-parse --git-dir)/mikromagic-checks-passed"
  }

  checks_pass_write_stamp() {
    local tree=$1 commit=$2
    printf 'tree %s\ncommit %s\n' "$tree" "$commit" > "$(checks_pass_stamp_file)"
  }

  # Reads tree id from stamp (supports legacy single-line stamps).
  checks_pass_read_tree() {
    local stamp line
    stamp=$(checks_pass_stamp_file)
    [ -f "$stamp" ] || return 1
    line=$(head -1 "$stamp")
    if [[ "$line" == tree\ * ]]; then
      echo "${line#tree }"
    else
      echo "$line"
    fi
  }

  checks_pass_read_commit() {
    local stamp
    stamp=$(checks_pass_stamp_file)
    [ -f "$stamp" ] || return 1
    sed -n 's/^commit //p' "$stamp" | head -1
  }

  checks_pass_tree_with_manifest_staged() {
    local idx tree
    idx=$(mktemp)
    export GIT_INDEX_FILE=$idx
    git read-tree HEAD
    git add .corrective-source-manifest.txt
    tree=$(git write-tree)
    unset GIT_INDEX_FILE
    rm -f "$idx"
    echo "$tree"
  }

  checks_pass_is_docs_only_path() {
    local path=$1
    case "$path" in
      *.md) return 0 ;;
      docs/*) return 0 ;;
      *) return 1 ;;
    esac
  }

  # True when every path changed between $1 and $2 (default HEAD) is documentation
  # or the corrective source manifest (manifest updates after doc edits are expected).
  checks_pass_diff_docs_only() {
    local from=${1:?} to=${2:-HEAD} path
    while IFS= read -r path; do
      [ -n "$path" ] || continue
      [ "$path" = .corrective-source-manifest.txt ] && continue
      checks_pass_is_docs_only_path "$path" || return 1
    done < <(git diff --name-only "$from" "$to" 2>/dev/null || true)
    return 0
  }

  # True when status is clean or only the manifest file is modified.
  checks_pass_manifest_only_dirty() {
    local status count
    status=$(git status --porcelain)
    [ -z "$status" ] && return 0
    count=$(printf '%s\n' "$status" | sed '/^$/d' | wc -l | tr -d ' ')
    [ "$count" -eq 1 ] && printf '%s\n' "$status" | grep -qx ' M .corrective-source-manifest.txt'
  }

  checks_pass_only_manifest_modified() {
    checks_pass_manifest_only_dirty
  }
}

if [ "${CHECKS_PASS_LIB_ONLY:-}" = 1 ]; then
  checks_pass_lib
  if [ "${1:-}" = invoke ]; then
    shift
    "$@"
  else
    echo "usage: CHECKS_PASS_LIB_ONLY=1 $0 invoke <function> [args...]" >&2
    exit 2
  fi
  exit $?
fi

cd "$(dirname "$0")/.."
checks_pass_lib
PY=${PYTHON:-.venv/bin/python}

if [ "${SKIP_CHECKS_TESTS:-0}" != 1 ]; then
  "$PY" scripts/run-tests.py
  npm run build
  node --test tests/*.test.mjs
fi

node scripts/generate-source-manifest.mjs >/dev/null

if checks_pass_only_manifest_modified; then
  tree=$(checks_pass_tree_with_manifest_staged)
  commit=$(git rev-parse HEAD)
  checks_pass_write_stamp "$tree" "$commit"
  echo "Checks passed; commit .corrective-source-manifest.txt (manifest was regenerated). Pass recorded for tree $(git rev-parse --short "$tree") at commit $(git rev-parse --short "$commit") — deploy will not rerun checks for that tree."
elif [ -z "$(git status --porcelain)" ]; then
  checks_pass_write_stamp "$(git rev-parse 'HEAD^{tree}')" "$(git rev-parse HEAD)"
  echo "Checks passed for tree $(git rev-parse --short 'HEAD^{tree}') (commit $(git rev-parse --short HEAD))"
else
  echo "Checks passed; uncommitted changes, so no deploy record was written"
fi
