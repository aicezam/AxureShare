#!/bin/sh
set -eu

cd /workspace

if [ ! -f requirements.txt ]; then
  echo "未找到 requirements.txt，请确认源码目录已挂载到 /workspace"
  exit 1
fi

mkdir -p instance uploads/prototypes uploads/source_files uploads/attachments

python -m pip install -r requirements.txt -i "${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

flask db upgrade

exec python app.py
