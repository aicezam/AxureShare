"""原型文件存储与解压服务。"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import Callable

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class ZipFileInvalidError(Exception):
    """ZIP 文件无效或损坏。"""


@dataclass(frozen=True)
class PrototypeFilesService:
    """原型相关文件的保存、删除与解压。"""

    prototypes_folder: str
    source_files_folder: str
    attachments_folder: str

    def ensure_folders(self) -> None:
        """确保必要目录存在。"""

        os.makedirs(self.prototypes_folder, exist_ok=True)
        os.makedirs(self.source_files_folder, exist_ok=True)
        os.makedirs(self.attachments_folder, exist_ok=True)

    def save_attachment(self, proto_uuid: str, attach_file: FileStorage) -> tuple[str, str]:
        """保存附件文件并返回 (原文件名, 保存名)。"""

        original_filename = attach_file.filename or ""
        safe_filename = secure_filename(original_filename)
        savename = f"{proto_uuid}_{safe_filename}"
        attach_filepath = os.path.join(self.attachments_folder, savename)
        attach_file.save(attach_filepath)
        return original_filename, savename

    def save_source(self, proto_uuid: str, source_file: FileStorage) -> tuple[str, str]:
        """保存源文件并返回 (原文件名, 保存名)。"""

        original_filename = source_file.filename or ""
        safe_filename = secure_filename(original_filename)
        savename = f"{proto_uuid}_{safe_filename}"
        source_filepath = os.path.join(self.source_files_folder, savename)
        source_file.save(source_filepath)
        return original_filename, savename

    def delete_attachment(self, savename: str | None) -> None:
        """删除附件文件。"""

        if not savename:
            return
        fp = os.path.join(self.attachments_folder, savename)
        if os.path.exists(fp):
            os.remove(fp)

    def delete_source(self, savename: str | None) -> None:
        """删除源文件。"""

        if not savename:
            return
        fp = os.path.join(self.source_files_folder, savename)
        if os.path.exists(fp):
            os.remove(fp)

    def delete_prototype_folder(self, proto_uuid: str) -> None:
        """删除原型解压目录。"""

        proto_path = os.path.join(self.prototypes_folder, proto_uuid)
        if os.path.exists(proto_path):
            shutil.rmtree(proto_path)

    def save_zip_and_extract(
        self,
        proto_uuid: str,
        zip_file: FileStorage,
        overwrite: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """保存 ZIP 并解压，返回解压目录路径。"""

        proto_path = os.path.join(self.prototypes_folder, proto_uuid)
        if overwrite and os.path.exists(proto_path):
            shutil.rmtree(proto_path)
        os.makedirs(proto_path, exist_ok=True)

        zip_filename = secure_filename(zip_file.filename or "")
        zip_filepath = os.path.join(proto_path, zip_filename)
        zip_file.save(zip_filepath)
        try:
            with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
                infos = zip_ref.infolist()
                total_bytes = sum(info.file_size for info in infos)
                extracted_bytes = 0
                if progress_callback:
                    progress_callback(extracted_bytes, total_bytes)
                for info in infos:
                    zip_ref.extract(info, proto_path)
                    extracted_bytes += info.file_size
                    if progress_callback:
                        progress_callback(extracted_bytes, total_bytes)
        except zipfile.BadZipFile as e:
            raise ZipFileInvalidError(str(e)) from e
        finally:
            if os.path.exists(zip_filepath):
                os.remove(zip_filepath)
        return proto_path
