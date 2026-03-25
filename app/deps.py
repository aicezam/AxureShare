"""应用依赖注入的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass

from hashids import Hashids

from app.services.ai import AiService
from app.services.prototype_files import PrototypeFilesService
from app.services.prototypes import PrototypeService
from app.services.projects import ProjectService


@dataclass(frozen=True)
class AppDeps:
    """路由层使用的依赖集合。"""

    hashids: Hashids
    ai_service: AiService
    project_service: ProjectService
    prototype_service: PrototypeService
    prototype_files_service: PrototypeFilesService

