#!/usr/bin/env bash
# Locate project-level AI-editor config and report git status.
# Read-only. Safe to run any time.
#
# Usage: ./find-project-configs.sh [root ...]
#        defaults to the current directory
set -euo pipefail

if [ "$#" -eq 0 ]; then
  ROOTS=(".")
else
  ROOTS=("$@")
fi

for root in "${ROOTS[@]}"; do
  while IFS= read -r -d '' match; do
    dir=$(dirname "$match")
    if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      repo_root=$(git -C "$dir" rev-parse --show-toplevel)
      rel=$(realpath --relative-to="$repo_root" "$match")
      if git -C "$repo_root" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
        status="TRACKED (committed with the repo)"
      elif git -C "$repo_root" check-ignore -q "$rel" 2>/dev/null; then
        status="gitignored (local-only)"
      else
        status="untracked (local-only)"
      fi
    else
      status="not inside a git repo"
    fi
    echo "$match  ->  $status"
  done < <(find "$root" \
    \( -iname .claude -o -iname .mcp.json -o -iname .cursor -o -iname .cursorrules \) \
    -not -path '*/node_modules/*' \
    -not -path '*/.cache/*' \
    -not -path '*/.git/*' \
    -print0 2>/dev/null)
done
