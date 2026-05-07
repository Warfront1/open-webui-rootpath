#!/bin/bash
set -e

SENTINEL="/__WEBUI_ROOT_PATH__"
ROOT_PATH="${WEBUI_ROOT_PATH:-}"

# Normalize the root path: ensure leading slash, no trailing slash
if [ "$ROOT_PATH" = "/" ] || [ -z "$ROOT_PATH" ]; then
    REPLACEMENT=""
else
    REPLACEMENT="${ROOT_PATH%/}"
    REPLACEMENT="${REPLACEMENT#/}"
    REPLACEMENT="/${REPLACEMENT}"
fi

if grep -rq "$SENTINEL" /app/build/ 2>/dev/null; then
    echo "=== Replacing sentinel root path with: ${REPLACEMENT:-/(root)} ==="
    find /app/build -type f \( -name '*.html' -o -name '*.js' -o -name '*.json' \) -exec sed -i "s|${SENTINEL}|${REPLACEMENT}|g" {} +
    echo "=== Done ==="
else
    echo "=== No sentinel root path found in /app/build/ (already replaced or not present) ==="
fi

exec "$@"