"""应用创建与依赖组装。"""

from __future__ import annotations

import os

from flask import Flask
from hashids import Hashids

from app.config import build_app_config
from app.deps import AppDeps
from app.extensions import db, login_manager, migrate
from app.models import User
from app.routes import register_routes
from app.services.ai import AiService
from app.services.bootstrap import ensure_default_admin
from app.services.prototype_files import PrototypeFilesService
from app.services.prototypes import PrototypeService
from app.services.projects import ProjectService
from app.utils.env_loader import load_dotenv_file, load_keys_from_markdown
from app.utils.filters import datetime_cn

def create_app() -> Flask:
    """创建并配置 Flask 应用。"""

    base_dir = os.path.dirname(os.path.dirname(__file__))
    load_dotenv_file(os.path.join(base_dir, ".env"))
    load_keys_from_markdown(os.path.join(base_dir, "AI相关文档", "apil-key.md"))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        instance_relative_config=False,
    )
    
    # 注册过滤器
    app.jinja_env.filters["datetime_cn"] = datetime_cn

    app.config.update(build_app_config(base_dir=base_dir))

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "请先登录以访问此页面。"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def _load_user(user_id: str) -> User | None:
        """按用户 ID 加载登录用户。"""

        try:
            uid = int(user_id)
        except Exception:
            return None
        return db.session.get(User, uid)

    hashids = Hashids(
        salt=str(app.config.get("HASHIDS_SALT") or "this is my very secret salt, change it"),
        min_length=int(app.config.get("HASHIDS_MIN_LENGTH") or 6),
    )

    ai_service = AiService(
        base_dir=base_dir,
        prototypes_folder=str(app.config["PROTOTYPES_FOLDER"]),
        instance_folder=str(app.config["INSTANCE_FOLDER"]),
    )
    files_service = PrototypeFilesService(
        prototypes_folder=str(app.config["PROTOTYPES_FOLDER"]),
        source_files_folder=str(app.config["SOURCE_FILES_FOLDER"]),
        attachments_folder=str(app.config["ATTACHMENTS_FOLDER"]),
    )
    project_service = ProjectService()
    prototype_service = PrototypeService(ai_service=ai_service, files_service=files_service)

    deps = AppDeps(
        hashids=hashids,
        ai_service=ai_service,
        project_service=project_service,
        prototype_service=prototype_service,
        prototype_files_service=files_service,
    )
    register_routes(app=app, deps=deps)

    with app.app_context():
        ensure_default_admin()
        ai_service.init_storage()
        files_service.ensure_folders()

    return app
