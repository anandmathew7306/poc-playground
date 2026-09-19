#!/usr/bin/env bash
# Detect install method and data footprint for Cursor and Claude Code.
# Read-only. Safe to run any time.
set -euo pipefail

echo "=== Package manager ==="
if command -v dnf >/dev/null 2>&1; then
  PKG_MGR=dnf
elif command -v apt >/dev/null 2>&1; then
  PKG_MGR=apt
else
  PKG_MGR=unknown
fi
echo "detected: $PKG_MGR"

echo ""
echo "=== Cursor ==="
case "$PKG_MGR" in
  dnf) rpm -qa | grep -i '^cursor-' || echo "not installed via rpm" ;;
  apt) dpkg -l 2>/dev/null | grep -i '^ii.*cursor ' || echo "not installed via apt" ;;
  *) echo "skip package check" ;;
esac
command -v cursor >/dev/null 2>&1 && command -v cursor || echo "cursor binary not on PATH"
if [ "$PKG_MGR" = dnf ]; then
  ls /etc/yum.repos.d/ 2>/dev/null | grep -iE 'cursor|anysphere' || echo "no dnf repo file found"
elif [ "$PKG_MGR" = apt ]; then
  ls /etc/apt/sources.list.d/ 2>/dev/null | grep -iE 'cursor|anysphere' || echo "no apt repo file found"
fi

echo ""
echo "=== Claude Code ==="
command -v claude >/dev/null 2>&1 && command -v claude || echo "claude binary not on PATH"
[ -d "$HOME/.local/share/claude" ] && echo "native install versions dir present"
[ -f "$HOME/.local/share/applications/claude-code-url-handler.desktop" ] && \
  echo "desktop launcher present"

echo ""
echo "=== Data paths ==="
for d in \
  "$HOME/.config/Cursor" \
  "$HOME/.cursor" \
  "$HOME/.cache/Cursor" \
  "$HOME/.claude" \
  "$HOME/.claude.json" \
  "$HOME/.local/share/claude"
do
  if [ -e "$d" ]; then
    size=$(du -sh "$d" 2>/dev/null | cut -f1)
    echo "EXISTS (${size:-?}): $d"
  else
    echo "not found: $d"
  fi
done
