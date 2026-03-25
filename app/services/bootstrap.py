"""启动阶段的初始化逻辑。"""

from __future__ import annotations

from app.extensions import db
from app.models import User


def ensure_default_admin() -> None:
    """确保存在默认管理员账户。"""

    if User.query.filter_by(username="admin").first():
        return
    admin_user = User(username="admin", role="admin")
    admin_user.set_password("123456")
    db.session.add(admin_user)
    db.session.commit()

