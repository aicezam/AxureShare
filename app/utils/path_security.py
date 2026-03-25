"""路径安全工具。"""

from __future__ import annotations

import os


def is_within_directory(base_dir: str, target_path: str) -> bool:
    """判断目标路径是否在指定目录内。"""

    base_real = os.path.realpath(base_dir)
    target_real = os.path.realpath(target_path)
    return target_real.startswith(base_real)

