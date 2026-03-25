"""应用配置构建。"""

from __future__ import annotations

import os
from typing import Any


def build_app_config(base_dir: str) -> dict[str, Any]:
    """构建应用运行所需配置。"""

    upload_folder = os.path.join(base_dir, "uploads")
    prototypes_folder = os.path.join(upload_folder, "prototypes")
    source_files_folder = os.path.join(upload_folder, "source_files")
    attachments_folder = os.path.join(upload_folder, "attachments")
    instance_folder = os.path.join(base_dir, "instance")

    secret_key = os.environ.get("SECRET_KEY", "").strip() or "a-very-secure-and-random-secret-key-please-change"

    return {
        "SECRET_KEY": secret_key,
        "SQLALCHEMY_DATABASE_URI": os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///app.db"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "UPLOAD_FOLDER": upload_folder,
        "PROTOTYPES_FOLDER": prototypes_folder,
        "SOURCE_FILES_FOLDER": source_files_folder,
        "ATTACHMENTS_FOLDER": attachments_folder,
        "INSTANCE_FOLDER": instance_folder,
        "HASHIDS_SALT": os.environ.get("HASHIDS_SALT", "").strip() or "this is my very secret salt, change it",
        "HASHIDS_MIN_LENGTH": int(os.environ.get("HASHIDS_MIN_LENGTH", "6")),
    }

