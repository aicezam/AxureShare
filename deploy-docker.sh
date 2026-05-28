#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT_DIR"

IMAGE_NAME="${AXURE_SHARE_IMAGE:-axure-share-runtime:latest}"
CONTAINER_NAME="${AXURE_SHARE_CONTAINER:-axure-share}"
APP_PORT="${AXURE_SHARE_PORT:-7855}"

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

mkdir -p instance uploads/prototypes uploads/source_files uploads/attachments

docker build -t "$IMAGE_NAME" .

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --env-file .env \
  -e FLASK_APP=app.py \
  -e PYTHONUNBUFFERED=1 \
  -e PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
  -p "$APP_PORT:7855" \
  -v "$PROJECT_DIR:/workspace" \
  "$IMAGE_NAME"

echo "部署完成：http://localhost:$APP_PORT"
echo "源码目录已挂载到容器 /workspace，修改代码后执行 docker restart $CONTAINER_NAME 即可生效"
