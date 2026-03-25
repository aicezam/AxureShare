"""文本文件读取工具。"""

from __future__ import annotations


def read_text_file(file_path: str) -> str:
    """读取文本文件内容，自动兼容 UTF-8 与 GBK。"""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="gbk", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

