#!/usr/bin/env bash
set -euo pipefail

PKG="@williamzujkowski/live-coding-music-mcp"

TARGET=""
for d in /root/.npm/_npx/*; do
  candidate="$d/node_modules/$PKG/dist/services/SessionManager.js"
  if [[ -f "$candidate" ]]; then
    TARGET="$candidate"
  fi
done

# Materialize package in npm cache when not present yet.
if [[ -z "$TARGET" ]]; then
  npm exec --yes --package "$PKG" -- node -e "process.exit(0)" >/dev/null 2>&1 || true
  for d in /root/.npm/_npx/*; do
    candidate="$d/node_modules/$PKG/dist/services/SessionManager.js"
    if [[ -f "$candidate" ]]; then
      TARGET="$candidate"
    fi
  done
fi

if [[ -z "$TARGET" ]]; then
  echo "Failed to locate SessionManager.js in npx cache" >&2
  exit 1
fi

# Upstream currently blocks media resources in browser routing, which can silence audio playback.
# Keep image/font blocking, but allow media resources.
sed -i "s/\['image', 'font', 'media'\]/['image', 'font']/g" "$TARGET"

INDEX_FILE="${TARGET%/services/SessionManager.js}/index.js"
if [[ ! -f "$INDEX_FILE" ]]; then
  echo "Failed to locate MCP index.js at $INDEX_FILE" >&2
  exit 1
fi

exec node "$INDEX_FILE"
