"""SQLAlchemy 数据模型定义。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


user_group_association = db.Table(
    "user_group_association",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
)
user_view_permissions = db.Table(
    "user_view_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("prototype_id", db.Integer, db.ForeignKey("prototype.id"), primary_key=True),
)
user_edit_permissions = db.Table(
    "user_edit_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("prototype_id", db.Integer, db.ForeignKey("prototype.id"), primary_key=True),
)
group_view_permissions = db.Table(
    "group_view_permissions",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("prototype_id", db.Integer, db.ForeignKey("prototype.id"), primary_key=True),
)
group_edit_permissions = db.Table(
    "group_edit_permissions",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("prototype_id", db.Integer, db.ForeignKey("prototype.id"), primary_key=True),
)
user_view_project_permissions = db.Table(
    "user_view_project_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
)
user_edit_project_permissions = db.Table(
    "user_edit_project_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
)
group_view_project_permissions = db.Table(
    "group_view_project_permissions",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
)
group_edit_project_permissions = db.Table(
    "group_edit_project_permissions",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    """用户模型。"""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20), nullable=False, default="user")
    groups = db.relationship("Group", secondary=user_group_association, back_populates="users")
    api_token = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid.uuid4()))

    def set_password(self, password: str) -> None:
        """设置密码。"""

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """校验密码。"""

        return check_password_hash(self.password_hash or "", password)


class Group(db.Model):
    """用户组模型。"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    users = db.relationship("User", secondary=user_group_association, back_populates="groups")


class Project(db.Model):
    """项目模型。"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User", backref=db.backref("owned_projects", lazy=True))
    prototypes = db.relationship("Prototype", backref="project", lazy=True)
    viewing_users = db.relationship(
        "User",
        secondary=user_view_project_permissions,
        lazy="subquery",
        backref=db.backref("viewable_projects", lazy=True),
    )
    editing_users = db.relationship(
        "User",
        secondary=user_edit_project_permissions,
        lazy="subquery",
        backref=db.backref("editable_projects", lazy=True),
    )
    viewing_groups = db.relationship(
        "Group",
        secondary=group_view_project_permissions,
        lazy="subquery",
        backref=db.backref("viewable_projects", lazy=True),
    )
    editing_groups = db.relationship(
        "Group",
        secondary=group_edit_project_permissions,
        lazy="subquery",
        backref=db.backref("editable_projects", lazy=True),
    )

    @property
    def last_activity_at(self) -> datetime:
        """返回项目本身更新时间或最近原型更新时间中的较晚者。"""
        if not self.prototypes:
            return self.updated_at
        
        proto_times = [p.updated_at for p in self.prototypes if p.updated_at]
        if not proto_times:
            return self.updated_at
            
        latest_proto_time = max(proto_times)
        return max(self.updated_at, latest_proto_time)


class Prototype(db.Model):
    """原型模型。"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_savename = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    source_filename = db.Column(db.String(255), nullable=True)
    source_savename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    access_password = db.Column(db.String(200), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship(
        "User",
        backref=db.backref("owned_prototypes", lazy=True),
        foreign_keys=[owner_id],
    )
    updater_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updater = db.relationship("User", foreign_keys=[updater_id])
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    resource_type = db.Column(db.String(20), nullable=False, server_default="axure")  # axure, static, url
    target_url = db.Column(db.String(500), nullable=True)
    rule_keywords = db.Column(db.Text, nullable=True, default='["jiao_hu_gui_ze"]')
    viewing_users = db.relationship(
        "User",
        secondary=user_view_permissions,
        lazy="subquery",
        backref=db.backref("viewable_prototypes", lazy=True),
    )
    editing_users = db.relationship(
        "User",
        secondary=user_edit_permissions,
        lazy="subquery",
        backref=db.backref("editable_prototypes", lazy=True),
    )
    viewing_groups = db.relationship(
        "Group",
        secondary=group_view_permissions,
        lazy="subquery",
        backref=db.backref("viewable_prototypes", lazy=True),
    )
    editing_groups = db.relationship(
        "Group",
        secondary=group_edit_permissions,
        lazy="subquery",
        backref=db.backref("editable_prototypes", lazy=True),
    )
    attachments = db.relationship(
        "PrototypeAttachment",
        backref="prototype",
        lazy=True,
        cascade="all, delete-orphan",
    )
    view_logs = db.relationship(
        "ViewLog",
        backref="prototype",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def set_access_password(self, password: str) -> None:
        """设置公开访问密码。"""

        self.access_password = password

    def check_access_password(self, password: str) -> bool:
        """校验公开访问密码。"""

        if not self.access_password:
            return False
        return self.access_password == password

    def get_view_stats(self, exclude_user_id: int | None = None) -> dict[str, int]:
        """获取浏览统计（排除指定用户）。"""
        total_views = 0
        unique_viewers = set()
        for log in self.view_logs:
            if exclude_user_id and log.user_id == exclude_user_id:
                continue
            total_views += 1
            if log.user_id:
                unique_viewers.add(f"u_{log.user_id}")
            else:
                unique_viewers.add(f"ip_{log.ip}")
        return {"views": total_views, "viewers": len(unique_viewers)}


class PrototypeAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prototype_id = db.Column(db.Integer, db.ForeignKey("prototype.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    savename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ViewLog(db.Model):
    """原型浏览记录。"""

    id = db.Column(db.Integer, primary_key=True)
    prototype_id = db.Column(db.Integer, db.ForeignKey("prototype.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user = db.relationship("User", backref=db.backref("view_logs", lazy=True))
    ip = db.Column(db.String(45), nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
