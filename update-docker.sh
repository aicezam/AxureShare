#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT_DIR"

CONTAINER_NAME="${AXURE_SHARE_CONTAINER:-axure-share}"

if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  git pull
fi

docker restart "$CONTAINER_NAME"

echo "代码已更新，容器已重启：http://localhost:${AXURE_SHARE_PORT:-7855}"
