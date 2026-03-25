"""原型业务服务。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai import AiService
from app.services.prototype_files import PrototypeFilesService


@dataclass(frozen=True)
class PrototypeService:
    """原型相关的业务能力封装。"""

    ai_service: AiService
    files_service: PrototypeFilesService

    def process_ai(self, prototype_id: int, proto_path: str) -> None:
        """对原型目录执行 AI 处理。"""

        self.ai_service.process_prototype(prototype_id=prototype_id, proto_root_dir=proto_path)

