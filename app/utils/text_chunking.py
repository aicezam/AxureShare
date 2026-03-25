"""文本切分工具。"""

from __future__ import annotations

import re


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    """将长文本按段落与长度切分成多个块。"""

    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []

    blocks = [b.strip() for b in re.split(r"\n{2,}", normalized) if b.strip()]
    chunks: list[str] = []
    cur = ""
    for b in blocks:
        if not cur:
            cur = b
            continue
        if len(cur) + 2 + len(b) <= max_chars:
            cur = cur + "\n\n" + b
        else:
            chunks.append(cur)
            cur = b
    if cur:
        chunks.append(cur)

    merged: list[str] = []
    for c in chunks:
        if len(c) <= max_chars:
            merged.append(c)
        else:
            for i in range(0, len(c), max_chars):
                merged.append(c[i : i + max_chars])
    return merged

