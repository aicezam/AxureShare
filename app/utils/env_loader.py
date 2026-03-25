"""环境变量加载工具。"""

from __future__ import annotations

import os


def load_dotenv_file(dotenv_path: str) -> None:
    """从 .env 文件加载环境变量（不覆盖已存在变量）。"""

    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def load_keys_from_markdown(markdown_path: str) -> None:
    """从 Markdown 的 key:value 行加载环境变量（不覆盖已存在变量）。"""

    if not os.path.exists(markdown_path):
        return
    try:
        with open(markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(markdown_path, "r", encoding="gbk", errors="ignore") as f:
            content = f.read()
    except Exception:
        return

    if not content:
        return

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        value = v.strip()
        if not key or not value:
            continue
        if key not in os.environ or not os.environ.get(key, "").strip():
            os.environ[key] = value

