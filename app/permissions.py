"""权限检查与装饰器。"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import abort
from flask_login import current_user

from app.models import Project, Prototype

F = TypeVar("F", bound=Callable[..., Any])


def admin_required(func: F) -> F:
    """限制仅管理员访问。"""

    @wraps(func)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return func(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def has_view_permission_project(project: Project | None) -> bool:
    """判断当前用户是否能查看项目。"""

    if not project or not current_user.is_authenticated:
        return False
    if current_user.role == "admin" or project.owner_id == current_user.id:
        return True
    if current_user in project.viewing_users or current_user in project.editing_users:
        return True
    for group in current_user.groups:
        if group in project.viewing_groups or group in project.editing_groups:
            return True
    return False


def has_edit_permission_project(project: Project | None) -> bool:
    """判断当前用户是否能编辑项目。"""

    if not project or not current_user.is_authenticated:
        return False
    if current_user.role == "admin" or project.owner_id == current_user.id:
        return True
    if current_user in project.editing_users:
        return True
    for group in current_user.groups:
        if group in project.editing_groups:
            return True
    return False


def has_view_permission(proto: Prototype) -> bool:
    """判断当前用户是否能查看原型。"""

    if not current_user.is_authenticated:
        return False
    if current_user.role == "admin" or proto.owner_id == current_user.id:
        return True
    if proto.project and has_view_permission_project(proto.project):
        return True
    if current_user in proto.viewing_users or current_user in proto.editing_users:
        return True
    for group in current_user.groups:
        if group in proto.viewing_groups or group in proto.editing_groups:
            return True
    return False


def has_edit_permission(proto: Prototype) -> bool:
    """判断当前用户是否能编辑原型。"""

    if not current_user.is_authenticated:
        return False
    if current_user.role == "admin" or proto.owner_id == current_user.id:
        return True
    if proto.project and has_edit_permission_project(proto.project):
        return True
    if current_user in proto.editing_users:
        return True
    for group in current_user.groups:
        if group in proto.editing_groups:
            return True
    return False

