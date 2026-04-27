"""路由注册与视图函数实现。"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import random
import re
import urllib.parse
import uuid
import zipfile
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, TypeVar

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import desc, exc
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage

from app.deps import AppDeps
from app.extensions import db, login_manager
from app.forms import (
    AdminProfileForm,
    CreateUserForm,
    EditUserForm,
    GroupForm,
    LoginForm,
    ProjectForm,
    PrototypeEditForm,
    PrototypeUploadForm,
    PublicPasswordForm,
)
from app.models import Group, Project, Prototype, PrototypeAttachment, User, ViewLog
from app.permissions import admin_required, has_edit_permission, has_edit_permission_project, has_view_permission, has_view_permission_project
from app.services.prototype_files import ZipFileInvalidError
from app.utils.html_rules import inject_ai_widget_into_html, remove_ai_widget_from_html
from app.utils.path_security import is_within_directory
from app.utils.text_files import read_text_file
from app.utils.network import get_remote_ip

F = TypeVar("F", bound=Callable[..., Any])


def register_routes(app: Flask, deps: AppDeps) -> None:
    """注册全部路由与错误处理。"""

    def default_ai_answer() -> str:
        """AI 无法回答时的默认文案。"""

        return "关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。"

    upload_progress: dict[str, dict[str, Any]] = {}

    def is_previewable_file(filename: str | None) -> bool:
        ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
        return ext in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}

    @app.after_request
    def add_api_cors_headers(response: Response) -> Response:
        if request.path.startswith("/api/"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return response

    @app.route("/api/<path:subpath>", methods=["OPTIONS"])
    def api_options(subpath: str) -> Response:
        return add_api_cors_headers(Response(status=204))

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """创建数据库表并初始化管理员账户。"""

        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin_user = User(username="admin", role="admin")
            admin_user.set_password("123456")
            db.session.add(admin_user)
            db.session.commit()

    def token_required(func: F) -> F:
        """API Token 鉴权装饰器。"""

        @wraps(func)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            token: str | None = None
            if "Authorization" in request.headers:
                try:
                    token = request.headers["Authorization"].split(" ")[1]
                except Exception:
                    return jsonify({"message": "Token is missing or malformed!"}), 401

            if not token:
                return jsonify({"message": "Token is missing!"}), 401

            user = User.query.filter_by(api_token=token).first()
            if not user:
                return jsonify({"message": "Token is invalid!"}), 401

            login_user(user)
            return func(*args, **kwargs)

        return decorated  # type: ignore[return-value]

    @app.route("/")
    @login_required
    def dashboard() -> str:
        all_projects = Project.query.options(joinedload(Project.prototypes)).order_by(desc(Project.name)).all()
        visible_projects = [p for p in all_projects if has_view_permission_project(p)]
        return render_template(
            "dashboard.html",
            projects=visible_projects,
            has_edit_permission_project=has_edit_permission_project,
        )

    @app.route("/prototypes/unassigned")
    @login_required
    def unassigned_prototypes() -> str:
        items = Prototype.query.filter(Prototype.project_id.is_(None)).order_by(desc(Prototype.name)).all()
        visible_unassigned = [p for p in items if has_view_permission(p)]
        return render_template(
            "unassigned_prototypes.html",
            prototypes=visible_unassigned,
            has_edit_permission=has_edit_permission,
            hashids=deps.hashids,
        )

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str:
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                session.pop("captcha_answer", None)
                session.pop("captcha_question", None)
                next_page = request.args.get("next")
                return redirect(next_page or url_for("dashboard"))
            flash("登录失败，请检查用户名和密码。", "danger")

        num1 = random.randint(0, 10)
        num2 = random.randint(0, 10)
        operator = random.choice(["+", "-"])
        if operator == "-" and num1 < num2:
            num1, num2 = num2, num1
        session["captcha_answer"] = num1 + num2 if operator == "+" else num1 - num2
        session["captcha_question"] = f"{num1} {operator} {num2} = ?"
        return render_template("login.html", form=form)

    @app.route("/logout")
    def logout() -> str:
        logout_user()
        return redirect(url_for("login"))

    @app.route("/project/<int:project_id>")
    @login_required
    def project_dashboard(project_id: int) -> str:
        project = db.session.get(Project, project_id) or abort(404)
        if not has_view_permission_project(project):
            abort(403)
        prototypes = Prototype.query.filter_by(project_id=project.id).order_by(desc(Prototype.name)).all()
        return render_template(
            "project_dashboard.html",
            project=project,
            prototypes=prototypes,
            has_edit_permission_project=has_edit_permission_project,
            has_edit_permission=has_edit_permission,
            hashids=deps.hashids,
        )

    @app.route("/projects/create", methods=["GET", "POST"])
    @login_required
    def create_project() -> str:
        form = ProjectForm()
        if form.validate_on_submit():
            new_project = Project(name=form.name.data, owner_id=current_user.id)
            db.session.add(new_project)
            db.session.commit()
            flash(f'项目 "{new_project.name}" 创建成功! 现在可以为其配置权限。', "success")
            return redirect(url_for("edit_project", project_id=new_project.id))
        return render_template("create_project.html", form=form)

    @app.route("/projects/edit/<int:project_id>", methods=["GET", "POST"])
    @login_required
    def edit_project(project_id: int) -> str:
        project = db.session.get(Project, project_id) or abort(404)
        if not has_edit_permission_project(project):
            abort(403)

        form = ProjectForm(obj=project)
        if form.validate_on_submit():
            project.name = form.name.data
            project.updated_at = datetime.utcnow()
            project.viewing_users = User.query.filter(User.id.in_(request.form.getlist("viewing_users"))).all()
            project.editing_users = User.query.filter(User.id.in_(request.form.getlist("editing_users"))).all()
            project.viewing_groups = Group.query.filter(Group.id.in_(request.form.getlist("viewing_groups"))).all()
            project.editing_groups = Group.query.filter(Group.id.in_(request.form.getlist("editing_groups"))).all()
            db.session.commit()
            flash(f'项目 "{project.name}" 更新成功!', "success")
            return redirect(url_for("dashboard"))

        all_users = (
            User.query.filter(User.role != "admin", User.id != project.owner_id).order_by(User.username).all()
        )
        all_groups = Group.query.order_by(Group.name).all()
        return render_template("edit_project.html", form=form, project=project, users=all_users, groups=all_groups)

    @app.route("/projects/delete/<int:project_id>", methods=["POST"])
    @login_required
    def delete_project(project_id: int) -> str:
        project = db.session.get(Project, project_id) or abort(404)
        if not has_edit_permission_project(project):
            abort(403)
        for proto in project.prototypes:
            proto.project_id = None
        db.session.delete(project)
        db.session.commit()
        flash(f'项目 "{project.name}" 已删除，其内部原型已变为独立原型。', "success")
        return redirect(url_for("dashboard"))

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload() -> str:
        form = PrototypeUploadForm()
        if form.validate_on_submit():
            project_id = form.project_id.data if form.project_id.data != 0 else None
            if project_id is not None:
                project = db.session.get(Project, project_id)
                if not project or not has_edit_permission_project(project):
                    flash("没有权限上传到该项目。", "danger")
                    return redirect(url_for("upload"))
            proto = Prototype(
                name=form.name.data,
                project_id=project_id,
                resource_type=form.resource_type.data,
                target_url=form.target_url.data,
                description=form.description.data,
                owner_id=current_user.id,
                updater_id=current_user.id,
                is_public=bool(form.is_public.data),
            )
            if form.rule_keywords.data:
                keywords = [k.strip() for k in form.rule_keywords.data.replace("，", ",").split(",") if k.strip()]
                proto.rule_keywords = json.dumps(keywords, ensure_ascii=False)
            else:
                proto.rule_keywords = json.dumps(["jiao_hu_gui_ze"])

            if form.access_password.data:
                proto.set_access_password(form.access_password.data)
            db.session.add(proto)
            db.session.commit()

            proto.viewing_users = User.query.filter(User.id.in_(request.form.getlist("viewing_users"))).all()
            proto.editing_users = User.query.filter(User.id.in_(request.form.getlist("editing_users"))).all()
            proto.viewing_groups = Group.query.filter(Group.id.in_(request.form.getlist("viewing_groups"))).all()
            proto.editing_groups = Group.query.filter(Group.id.in_(request.form.getlist("editing_groups"))).all()

            attachment_files = request.files.getlist("attachment_files")
            for attach_file in attachment_files:
                if not attach_file or not attach_file.filename:
                    continue
                original_filename, savename = deps.prototype_files_service.save_attachment(
                    proto_uuid=proto.uuid,
                    attach_file=attach_file,
                )
                db.session.add(
                    PrototypeAttachment(
                        prototype_id=proto.id,
                        filename=original_filename,
                        savename=savename,
                    )
                )

            if form.source_file.data:
                original_filename, savename = deps.prototype_files_service.save_source(
                    proto_uuid=proto.uuid,
                    source_file=form.source_file.data,
                )
                proto.source_filename = original_filename
                proto.source_savename = savename

            if proto.resource_type != "url" and form.zip_file.data:
                try:
                    proto_path = deps.prototype_files_service.save_zip_and_extract(
                        proto_uuid=proto.uuid, zip_file=form.zip_file.data, overwrite=False
                    )
                    try:
                        deps.prototype_service.process_ai(prototype_id=proto.id, proto_path=proto_path)
                    except Exception:
                        app.logger.exception("AI处理原型失败")
                except ZipFileInvalidError:
                    db.session.delete(proto)
                    db.session.commit()
                    flash("上传失败：ZIP文件已损坏或格式不正确。", "danger")
                    return redirect(url_for("upload"))

            db.session.commit()
            flash("原型上传并配置成功！", "success")
            return redirect(url_for("dashboard"))

        all_users = User.query.filter(User.role != "admin", User.id != current_user.id).order_by(User.username).all()
        all_groups = Group.query.order_by(Group.name).all()
        return render_template("upload.html", form=form, users=all_users, groups=all_groups)

    @app.route("/edit/<int:proto_id>", methods=["GET", "POST"])
    @login_required
    def edit_prototype(proto_id: int) -> str:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        if not has_edit_permission(proto):
            abort(403)

        form = PrototypeEditForm(obj=proto)

        if request.method == "GET" and proto.rule_keywords:
            try:
                keywords = json.loads(proto.rule_keywords)
                if isinstance(keywords, list):
                    form.rule_keywords.data = ", ".join(keywords)
            except Exception:
                pass

        if form.validate_on_submit():
            proto.name = form.name.data
            proto.resource_type = form.resource_type.data
            proto.target_url = form.target_url.data
            proto.project_id = form.project_id.data if form.project_id.data != 0 else None
            proto.description = form.description.data

            new_keywords_json = None
            if form.rule_keywords.data:
                keywords = [k.strip() for k in form.rule_keywords.data.replace("，", ",").split(",") if k.strip()]
                new_keywords_json = json.dumps(keywords, ensure_ascii=False)
            else:
                new_keywords_json = json.dumps(["jiao_hu_gui_ze"])
            
            keywords_changed = proto.rule_keywords != new_keywords_json
            proto.rule_keywords = new_keywords_json

            proto.updater_id = current_user.id
            proto.is_public = bool(form.is_public.data)
            access_password = (form.access_password.data or "").strip()
            if access_password:
                # 直接赋值，确保是明文存储，绕过可能存在的旧版模型方法
                proto.access_password = access_password
            else:
                proto.access_password = None

            proto.viewing_users = User.query.filter(User.id.in_(request.form.getlist("viewing_users"))).all()
            proto.editing_users = User.query.filter(User.id.in_(request.form.getlist("editing_users"))).all()
            proto.viewing_groups = Group.query.filter(Group.id.in_(request.form.getlist("viewing_groups"))).all()
            proto.editing_groups = Group.query.filter(Group.id.in_(request.form.getlist("editing_groups"))).all()

            if request.form.get("delete_legacy_attachment") == "1":
                deps.prototype_files_service.delete_attachment(proto.attachment_savename)
                proto.attachment_filename = None
                proto.attachment_savename = None

            delete_attachment_ids = request.form.getlist("delete_attachments")
            if delete_attachment_ids:
                id_list: list[int] = []
                for raw_id in delete_attachment_ids:
                    try:
                        id_list.append(int(raw_id))
                    except ValueError:
                        continue
                if id_list:
                    attachments = (
                        PrototypeAttachment.query.filter(PrototypeAttachment.id.in_(id_list))
                        .filter(PrototypeAttachment.prototype_id == proto.id)
                        .all()
                    )
                    for attachment in attachments:
                        deps.prototype_files_service.delete_attachment(attachment.savename)
                        db.session.delete(attachment)

            attachment_files = request.files.getlist("attachment_files")
            for attach_file in attachment_files:
                if not attach_file or not attach_file.filename:
                    continue
                original_filename, savename = deps.prototype_files_service.save_attachment(
                    proto_uuid=proto.uuid, attach_file=attach_file
                )
                db.session.add(
                    PrototypeAttachment(
                        prototype_id=proto.id,
                        filename=original_filename,
                        savename=savename,
                    )
                )

            if request.form.get("source_action") == "delete" and not form.source_file.data:
                deps.prototype_files_service.delete_source(proto.source_savename)
                proto.source_filename = None
                proto.source_savename = None
            elif form.source_file.data:
                deps.prototype_files_service.delete_source(proto.source_savename)
                original_filename, savename = deps.prototype_files_service.save_source(
                    proto_uuid=proto.uuid, source_file=form.source_file.data
                )
                proto.source_filename = original_filename
                proto.source_savename = savename

            zip_processed = False
            if form.zip_file.data:
                try:
                    proto_path = deps.prototype_files_service.save_zip_and_extract(
                        proto_uuid=proto.uuid, zip_file=form.zip_file.data, overwrite=True
                    )
                except ZipFileInvalidError:
                    flash("更新失败：ZIP文件已损坏或格式不正确。", "danger")
                    return redirect(url_for("edit_prototype", proto_id=proto.id))
                try:
                    deps.prototype_service.process_ai(prototype_id=proto.id, proto_path=proto_path)
                    zip_processed = True
                except Exception:
                    app.logger.exception("AI处理原型失败")

            db.session.commit()

            if keywords_changed and not zip_processed:
                try:
                    proto_path = os.path.join(str(app.config["PROTOTYPES_FOLDER"]), proto.uuid)
                    deps.prototype_service.process_ai(prototype_id=proto.id, proto_path=proto_path)
                    flash("关键词更新，已触发AI重新处理。", "info")
                except Exception:
                    app.logger.exception("AI处理原型失败（关键词更新）")
            flash("原型更新成功！", "success")
            return redirect(url_for("dashboard"))

        if request.method == "GET":
            # 无论是否是哈希值，都直接显示数据库中的原始内容
            # 这样用户可以看到已设置的密码（如果是旧数据则显示哈希串，如果是新数据则显示明文）
            form.access_password.data = proto.access_password or ""
        all_users = User.query.filter(User.role != "admin", User.id != proto.owner_id).order_by(User.username).all()
        all_groups = Group.query.order_by(Group.name).all()
        return render_template("edit_prototype.html", form=form, proto=proto, users=all_users, groups=all_groups)

    @app.route("/delete_prototype/<int:proto_id>", methods=["POST"])
    @login_required
    def delete_prototype(proto_id: int) -> str:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        if not has_edit_permission(proto):
            abort(403)
        try:
            deps.prototype_files_service.delete_prototype_folder(proto.uuid)
            deps.prototype_files_service.delete_source(proto.source_savename)
            deps.prototype_files_service.delete_attachment(proto.attachment_savename)
            for attachment in proto.attachments:
                deps.prototype_files_service.delete_attachment(attachment.savename)
        except Exception as e:
            flash(f"删除文件时出错: {e}", "danger")
            return redirect(request.referrer or url_for("dashboard"))
        db.session.delete(proto)
        db.session.commit()
        flash(f'原型 "{proto.name}" 已成功删除。', "success")
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/download_attachment/<int:proto_id>")
    @login_required
    def download_attachment(proto_id: int) -> Response:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        if not has_view_permission(proto):
            abort(403)
        if not proto.attachment_savename:
            flash("该原型没有附件。", "warning")
            return redirect(request.referrer or url_for("dashboard"))
        file_path = os.path.join(str(app.config["ATTACHMENTS_FOLDER"]), proto.attachment_savename)
        return send_file(file_path, download_name=proto.attachment_filename, as_attachment=True)

    @app.route("/download_attachment_item/<int:attachment_id>")
    @login_required
    def download_attachment_item(attachment_id: int) -> Response:
        attachment = db.session.get(PrototypeAttachment, attachment_id) or abort(404)
        proto = attachment.prototype
        if not proto or not has_view_permission(proto):
            abort(403)
        file_path = os.path.join(str(app.config["ATTACHMENTS_FOLDER"]), attachment.savename)
        return send_file(file_path, download_name=attachment.filename, as_attachment=True)

    @app.route("/download_source/<int:proto_id>")
    @login_required
    def download_source(proto_id: int) -> Response:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        if not has_view_permission(proto):
            abort(403)
        if not proto.source_savename:
            flash("该原型没有可供下载的源文件。", "warning")
            return redirect(url_for("dashboard"))
        file_path = os.path.join(str(app.config["SOURCE_FILES_FOLDER"]), proto.source_savename)
        return send_file(file_path, download_name=proto.source_filename, as_attachment=True)

    @app.route("/preview_attachment/<int:proto_id>")
    def preview_attachment(proto_id: int) -> Response:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        verified = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not verified and not has_view_permission(proto):
            if proto.is_public and proto.access_password:
                return redirect(url_for("public_auth", short_id=deps.hashids.encode(proto.id)))
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            abort(403)
        if not proto.attachment_savename:
            abort(404)
        file_path = os.path.join(str(app.config["ATTACHMENTS_FOLDER"]), proto.attachment_savename)
        ext = os.path.splitext(proto.attachment_filename or "")[1].lower().lstrip(".")
        if ext not in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}:
            abort(404)
        mimetype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return send_file(file_path, download_name=proto.attachment_filename, mimetype=mimetype, as_attachment=False)

    @app.route("/preview_attachment_item/<int:attachment_id>")
    def preview_attachment_item(attachment_id: int) -> Response:
        attachment = db.session.get(PrototypeAttachment, attachment_id) or abort(404)
        proto = attachment.prototype
        verified = bool(
            proto
            and proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not verified and not (proto and has_view_permission(proto)):
            if proto and proto.is_public and proto.access_password:
                return redirect(url_for("public_auth", short_id=deps.hashids.encode(proto.id)))
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            abort(403)
        file_path = os.path.join(str(app.config["ATTACHMENTS_FOLDER"]), attachment.savename)
        ext = os.path.splitext(attachment.filename or "")[1].lower().lstrip(".")
        if ext not in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}:
            abort(404)
        mimetype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return send_file(file_path, download_name=attachment.filename, mimetype=mimetype, as_attachment=False)

    @app.route("/preview_source/<int:proto_id>")
    def preview_source(proto_id: int) -> Response:
        proto = db.session.get(Prototype, proto_id) or abort(404)
        verified = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not verified and not has_view_permission(proto):
            if proto.is_public and proto.access_password:
                return redirect(url_for("public_auth", short_id=deps.hashids.encode(proto.id)))
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            abort(403)
        if not proto.source_savename:
            abort(404)
        file_path = os.path.join(str(app.config["SOURCE_FILES_FOLDER"]), proto.source_savename)
        ext = os.path.splitext(proto.source_filename or "")[1].lower().lstrip(".")
        if ext not in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}:
            abort(404)
        mimetype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return send_file(file_path, download_name=proto.source_filename, mimetype=mimetype, as_attachment=False)

    @app.route("/api/view_stats/<short_id>")
    @login_required
    def api_view_stats(short_id: str) -> Response:
        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            abort(404)
        proto = db.session.get(Prototype, prototype_id_tuple[0]) or abort(404)
        if not has_view_permission(proto):
            abort(403)
            
        logs = ViewLog.query.options(joinedload(ViewLog.user)).filter_by(prototype_id=proto.id).all()
        
        # 聚合统计
        stats_map = {}
        for log in logs:
            # 排除自己? 需求说列表显示排除自己，但弹窗详情应该显示所有人，或者标记出自己？
            # 既然是“查看人数”点击出来的弹窗，应该显示详细列表。
            key = str(log.user_id) if log.user_id else f"ip_{log.ip}"
            username = log.user.username if log.user else "游客"
            
            if key not in stats_map:
                stats_map[key] = {
                    "account": username,
                    "ip": log.ip,
                    "count": 0,
                    "last_viewed": log.viewed_at
                }
            stats_map[key]["count"] += 1
            if log.viewed_at > stats_map[key]["last_viewed"]:
                stats_map[key]["last_viewed"] = log.viewed_at
        
        result = list(stats_map.values())
        result.sort(key=lambda x: x["last_viewed"], reverse=True)
        
        # 格式化时间
        for item in result:
            item["last_viewed"] = (item["last_viewed"] + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
            
        return jsonify({"stats": result})

    @app.route("/api/prototype_info/<short_id>")
    def api_prototype_info(short_id: str) -> Response:
        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            abort(404)
        proto = db.session.get(Prototype, prototype_id_tuple[0]) or abort(404)
        verified = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not verified and not has_view_permission(proto):
            if proto.is_public and proto.access_password:
                return jsonify({"message": "需要访问密码"}), 403
            if not current_user.is_authenticated:
                return jsonify({"message": "未授权"}), 401
            return jsonify({"message": "无权限"}), 403

        def format_size(size_bytes: int) -> str:
            units = ["B", "KB", "MB", "GB", "TB"]
            size = float(size_bytes)
            idx = 0
            while size >= 1024 and idx < len(units) - 1:
                size /= 1024
                idx += 1
            return f"{size:.2f}{units[idx]}"

        def folder_size(path: str) -> int:
            total = 0
            if not os.path.exists(path):
                return 0
            for root, _, files in os.walk(path):
                for fn in files:
                    try:
                        total += os.path.getsize(os.path.join(root, fn))
                    except OSError:
                        continue
            return total

        def format_dt(value: datetime | None) -> str:
            if not value:
                return "-"
            return (value + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

        def file_info(
            kind: str,
            filename: str | None,
            savename: str | None,
            download_url_override: str | None = None,
            preview_url_override: str | None = None,
        ) -> dict[str, Any] | None:
            if not filename or not savename:
                return None
            if kind == "attachment":
                base_dir = str(app.config["ATTACHMENTS_FOLDER"])
                download_url = download_url_override or url_for("download_attachment", proto_id=proto.id)
                preview_url = preview_url_override or url_for("preview_attachment", proto_id=proto.id)
            else:
                base_dir = str(app.config["SOURCE_FILES_FOLDER"])
                download_url = download_url_override or url_for("download_source", proto_id=proto.id)
                preview_url = preview_url_override or url_for("preview_source", proto_id=proto.id)
            file_path = os.path.join(base_dir, savename)
            size = 0
            try:
                size = os.path.getsize(file_path)
            except OSError:
                size = 0
            ext = os.path.splitext(filename)[1].lower().lstrip(".")
            previewable = ext in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}
            return {
                "name": filename,
                "size_bytes": size,
                "size_text": format_size(size),
                "download_url": download_url,
                "preview_url": preview_url if previewable else "",
            }

        proto_path = os.path.join(str(app.config["PROTOTYPES_FOLDER"]), proto.uuid)
        proto_size = folder_size(proto_path)
        attachments: list[dict[str, Any]] = []
        legacy_attachment = file_info(
            "attachment",
            proto.attachment_filename,
            proto.attachment_savename,
            download_url_override=url_for("download_attachment", proto_id=proto.id),
            preview_url_override=url_for("preview_attachment", proto_id=proto.id),
        )
        if legacy_attachment:
            attachments.append(legacy_attachment)
        for attachment in proto.attachments:
            attachment_info = file_info(
                "attachment",
                attachment.filename,
                attachment.savename,
                download_url_override=url_for("download_attachment_item", attachment_id=attachment.id),
                preview_url_override=url_for("preview_attachment_item", attachment_id=attachment.id),
            )
            if attachment_info:
                attachments.append(attachment_info)

        payload = {
            "name": proto.name,
            "size_bytes": proto_size,
            "size_text": format_size(proto_size),
            "attachment": legacy_attachment or (attachments[0] if attachments else None),
            "attachments": attachments,
            "source": file_info("source", proto.source_filename, proto.source_savename),
            "prototype_url": url_for("view_prototype", short_id=deps.hashids.encode(proto.id), _external=True),
            "updated_at_text": format_dt(proto.updated_at or proto.created_at),
            "updater_name": proto.updater.username if proto.updater else (proto.owner.username if proto.owner else "-"),
        }
        return jsonify(payload)

    @app.route("/public/auth/<short_id>", methods=["GET", "POST"])
    def public_auth(short_id: str) -> str:
        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            abort(404)
        proto = db.session.get(Prototype, prototype_id_tuple[0]) or abort(404)
        if not proto.is_public or not proto.access_password:
            return redirect(url_for("view_prototype", short_id=short_id))
        form = PublicPasswordForm()
        if form.validate_on_submit():
            if proto.check_access_password(form.password.data):
                session["verified_protos"] = session.get("verified_protos", []) + [proto.id]
                session.modified = True
                return redirect(url_for("view_prototype", short_id=short_id))
            flash("访问密码错误！", "danger")
        return render_template("public_password.html", form=form, proto=proto, short_id=short_id, hide_nav=True)

    @app.route("/v/<short_id>/")
    @app.route("/v/<short_id>/<path:filename>", strict_slashes=False)
    def view_prototype(short_id: str, filename: str | None = None) -> Response:
        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            abort(404)
        proto = db.session.get(Prototype, prototype_id_tuple[0]) or abort(404)

        # 记录浏览日志 (仅在访问入口时记录)
        if filename is None:
            user_id = current_user.id if current_user.is_authenticated else None
            db.session.add(ViewLog(prototype_id=proto.id, user_id=user_id, ip=get_remote_ip(request)))
            db.session.commit()

        # 如果是 URL 类型，直接跳转
        if proto.resource_type == "url" and proto.target_url:
            return redirect(proto.target_url)

        verified = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not verified and not has_view_permission(proto):
            if proto.is_public and proto.access_password:
                return redirect(url_for("public_auth", short_id=short_id))
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            abort(403)

        if filename:
            filename = urllib.parse.unquote(filename).replace("\\", "/").strip("/")

        proto_path = os.path.join(str(app.config["PROTOTYPES_FOLDER"]), proto.uuid)

        def render_prototype_html(html_path: str) -> Response | None:
            """按资源类型渲染原型 HTML。"""

            try:
                html = read_text_file(html_path)
                if not html:
                    return None
                if proto.resource_type == "axure":
                    rendered_html = inject_ai_widget_into_html(html)
                else:
                    rendered_html = remove_ai_widget_from_html(html)
                return Response(rendered_html, mimetype="text/html; charset=utf-8")
            except Exception:
                return None

        if filename is None:
            possible_entries = ["index.html", "start.html"]
            if proto.resource_type == "static":
                for entry in possible_entries:
                    entry_path = os.path.join(proto_path, entry)
                    if os.path.exists(entry_path):
                        rendered = render_prototype_html(entry_path)
                        if rendered:
                            return rendered
                dir_contents = os.listdir(proto_path) if os.path.exists(proto_path) else []
                sub_dirs = [d for d in dir_contents if os.path.isdir(os.path.join(proto_path, d))]
                if len(sub_dirs) == 1:
                    nested_path = os.path.join(proto_path, sub_dirs[0])
                    for entry in possible_entries:
                        entry_path = os.path.join(nested_path, entry)
                        if os.path.exists(entry_path):
                            rendered = render_prototype_html(entry_path)
                            if rendered:
                                return rendered

            for entry in possible_entries:
                if os.path.exists(os.path.join(proto_path, entry)):
                    entry_url = url_for("view_prototype", short_id=short_id, filename=entry)
                    return redirect(entry_url + "#g=1" if proto.resource_type == "axure" else entry_url)
            dir_contents = os.listdir(proto_path) if os.path.exists(proto_path) else []
            sub_dirs = [d for d in dir_contents if os.path.isdir(os.path.join(proto_path, d))]
            if len(sub_dirs) == 1:
                nested_path = os.path.join(proto_path, sub_dirs[0])
                for entry in possible_entries:
                    if os.path.exists(os.path.join(nested_path, entry)):
                        correct_filename = os.path.join(sub_dirs[0], entry).replace("\\", "/")
                        entry_url = url_for("view_prototype", short_id=short_id, filename=correct_filename)
                        return redirect(entry_url + "#g=1" if proto.resource_type == "axure" else entry_url)
            document_js_path = os.path.join(proto_path, "data", "document.js")
            if os.path.exists(document_js_path):
                doc_text = ""
                try:
                    doc_text = read_text_file(document_js_path)
                except Exception:
                    doc_text = ""
                if doc_text:
                    candidates = re.findall(r'["\']([^"\']+\.html(?:\?[^"\']*)?)["\']', doc_text)
                    for cand in candidates:
                        if "resources/" in cand:
                            continue
                        rel = cand.split("?", 1)[0].lstrip("/").strip()
                        if not rel:
                            continue
                        file_candidate = os.path.join(proto_path, rel)
                        if is_within_directory(proto_path, file_candidate) and os.path.exists(file_candidate):
                            entry_url = url_for("view_prototype", short_id=short_id, filename=rel)
                            return redirect(entry_url + "#g=1" if proto.resource_type == "axure" else entry_url)
                        encoded_segments = [urllib.parse.quote(seg) for seg in rel.split("/")]
                        encoded_rel = "/".join(encoded_segments)
                        file_candidate = os.path.join(proto_path, encoded_rel)
                        if is_within_directory(proto_path, file_candidate) and os.path.exists(file_candidate):
                            entry_url = url_for("view_prototype", short_id=short_id, filename=rel)
                            return redirect(entry_url + "#g=1" if proto.resource_type == "axure" else entry_url)
            flash("无法找到原型入口文件 (index.html 或 start.html)。", "danger")
            return redirect(url_for("dashboard"))

        file_path = os.path.join(proto_path, filename)
        if not os.path.exists(file_path):
            index_candidate = os.path.join(proto_path, filename, "index.html")
            if is_within_directory(proto_path, index_candidate) and os.path.exists(index_candidate):
                rendered = render_prototype_html(index_candidate)
                if rendered:
                    return rendered
        if is_within_directory(proto_path, file_path) and os.path.isdir(file_path):
            for entry in ["index.html", "start.html"]:
                entry_path = os.path.join(file_path, entry)
                if os.path.exists(entry_path):
                    rendered = render_prototype_html(entry_path)
                    if rendered:
                        return rendered
            abort(404)
        if not is_within_directory(proto_path, file_path) or not os.path.exists(file_path):
            encoded_segments = [urllib.parse.quote(seg) for seg in filename.split("/")]
            encoded_filename = "/".join(encoded_segments)
            file_path = os.path.join(proto_path, encoded_filename)
            if not is_within_directory(proto_path, file_path) or not os.path.exists(file_path):
                # 兼容 Axure 11 缺失的文件 (如 hintmanager.js)
                if filename.lower().endswith("hintmanager.js"):
                    return Response("", mimetype="application/javascript")
                if filename.lower().endswith("hintmanager.css"):
                    return Response("", mimetype="text/css")
                abort(404)
        if filename.lower().endswith(".svg"):
            return send_file(file_path, mimetype="image/svg+xml")
        if filename.lower().endswith(".html"):
            rendered = render_prototype_html(file_path)
            if rendered:
                return rendered
        guessed_mimetype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if filename.lower().endswith(".js"):
            guessed_mimetype = "application/javascript; charset=utf-8"
        elif filename.lower().endswith(".mjs"):
            guessed_mimetype = "application/javascript; charset=utf-8"
        elif filename.lower().endswith(".css"):
            guessed_mimetype = "text/css; charset=utf-8"
        return send_file(file_path, mimetype=guessed_mimetype)

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def user_profile() -> str:
        user_to_edit = db.session.get(User, current_user.id)
        form = AdminProfileForm(obj=user_to_edit)
        if form.validate_on_submit():
            try:
                if user_to_edit is None:
                    abort(404)
                if form.password.data:
                    user_to_edit.set_password(form.password.data)
                db.session.commit()
                flash("您的个人资料已更新。", "success")
                return redirect(url_for("user_profile"))
            except exc.IntegrityError:
                db.session.rollback()
                flash("该用户名已被占用，请选择其他用户名。", "danger")
        return render_template("admin/profile.html", form=form)

    @app.route("/admin/profile", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_profile() -> str:
        user_to_edit = db.session.get(User, current_user.id)
        form = AdminProfileForm(obj=user_to_edit)
        if form.validate_on_submit():
            try:
                if user_to_edit is None:
                    abort(404)
                if form.password.data:
                    user_to_edit.set_password(form.password.data)
                db.session.commit()
                flash("您的个人资料已更新。", "success")
                return redirect(url_for("admin_profile"))
            except exc.IntegrityError:
                db.session.rollback()
                flash("该用户名已被占用，请选择其他用户名。", "danger")
        return render_template("admin/profile.html", form=form)

    @app.route("/admin/users")
    @login_required
    @admin_required
    def user_list() -> str:
        users = User.query.all()
        return render_template("admin/users.html", users=users)

    @app.route("/admin/users/create", methods=["GET", "POST"])
    @login_required
    @admin_required
    def create_user() -> str:
        form = CreateUserForm()
        if form.validate_on_submit():
            if User.query.filter_by(username=form.username.data).first():
                flash("用户名已存在。", "danger")
            else:
                user = User(username=form.username.data)
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                flash(f"用户 {user.username} 创建成功。", "success")
                return redirect(url_for("user_list"))
        return render_template("admin/create_user.html", form=form)

    @app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def edit_user(user_id: int) -> str:
        user = db.session.get(User, user_id) or abort(404)
        form = EditUserForm()
        if form.validate_on_submit():
            if form.password.data:
                user.set_password(form.password.data)
                db.session.commit()
                flash(f"用户 {user.username} 的密码已更新。", "success")
                return redirect(url_for("user_list"))
        return render_template("admin/edit_user.html", form=form, user=user)

    @app.route("/admin/groups")
    @login_required
    @admin_required
    def group_list() -> str:
        groups = Group.query.order_by(Group.name).all()
        return render_template("admin/groups.html", groups=groups)

    @app.route("/admin/groups/create", methods=["GET", "POST"])
    @login_required
    @admin_required
    def create_group() -> str:
        form = GroupForm()
        if form.validate_on_submit():
            if Group.query.filter_by(name=form.name.data).first():
                flash("用户组名称已存在。", "danger")
            else:
                group = Group(name=form.name.data)
                db.session.add(group)
                db.session.commit()
                flash(f'用户组 "{group.name}" 创建成功。', "success")
                return redirect(url_for("group_list"))
        return render_template("admin/create_group.html", form=form)

    @app.route("/admin/groups/edit/<int:group_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def edit_group(group_id: int) -> str:
        group = db.session.get(Group, group_id) or abort(404)
        form = GroupForm(obj=group)
        if form.validate_on_submit():
            group.name = form.name.data
            user_ids = [int(i) for i in request.form.getlist("users")]
            group.users = User.query.filter(User.id.in_(user_ids)).all()
            db.session.commit()
            flash(f'用户组 "{group.name}" 更新成功。', "success")
            return redirect(url_for("group_list"))
        all_users = User.query.filter_by(role="user").order_by(User.username).all()
        return render_template("admin/edit_group.html", form=form, group=group, users=all_users)

    @app.route("/api/login", methods=["POST"])
    def api_login() -> Response:
        data = request.get_json()
        if not data or not data.get("username") or not data.get("password"):
            return jsonify({"message": "无法验证"}), 400

        user = User.query.filter_by(username=str(data.get("username"))).first()
        if user and user.check_password(str(data.get("password"))):
            if not user.api_token:
                user.api_token = str(uuid.uuid4())
                db.session.commit()
            return jsonify({"message": "登录成功", "token": user.api_token})
        return jsonify({"message": "用户名或密码错误"}), 401

    @app.route("/api/projects", methods=["GET"])
    @token_required
    def api_projects() -> Response:
        all_projects = Project.query.order_by(desc(Project.created_at)).all()
        visible_projects = [p for p in all_projects if has_edit_permission_project(p)]
        projects_data = [{"id": p.id, "name": p.name} for p in visible_projects]
        return jsonify({"projects": projects_data})

    @app.route("/api/upload", methods=["POST"])
    @token_required
    def api_upload() -> Response:
        zip_file = request.files.get("zip_file")
        files = request.files.getlist("files")
        zip_flag = str(request.args.get("zip") or request.form.get("zip") or "").lower() in {"1", "true", "yes"}
        name_raw = str(request.form.get("name") or request.args.get("name") or "").strip()
        path_raw = str(request.form.get("path") or request.args.get("path") or "").strip()
        upload_id = str(request.form.get("upload_id") or request.args.get("upload_id") or "").strip()
        extract_loaded = 0
        extract_total = 0

        def update_upload_progress(
            stage: str, loaded: int, total: int, done: bool = False, error: str | None = None
        ) -> None:
            if not upload_id:
                return
            payload: dict[str, Any] = {
                "stage": stage,
                "loaded": int(loaded),
                "total": int(total),
                "done": bool(done),
            }
            if error:
                payload["error"] = error
            upload_progress[upload_id] = payload

        def report_extract_progress(loaded: int, total: int) -> None:
            nonlocal extract_loaded, extract_total
            extract_loaded = loaded
            extract_total = total
            update_upload_progress("extract", loaded, total, False)

        if upload_id:
            update_upload_progress("received", 0, 0, False)

        def resolve_name() -> str:
            if name_raw:
                return name_raw
            if path_raw:
                decoded_path = urllib.parse.unquote(path_raw).strip()
                if decoded_path:
                    base = decoded_path.strip("/").split("/")[-1]
                    if base:
                        return base
            if zip_file and zip_file.filename:
                base = os.path.splitext(zip_file.filename)[0]
                if base:
                    return base
            if files:
                first_name = files[0].filename or ""
                base = os.path.splitext(first_name)[0]
                if base:
                    return base
            return ""

        name = resolve_name() or "未命名原型"
        is_public_raw = str(request.form.get("is_public") or request.args.get("is_public") or "").strip().lower()
        is_public = is_public_raw in {"1", "true", "yes", "on"}
        access_password = str(request.form.get("access_password") or request.args.get("access_password") or "").strip()

        project_id_str = request.form.get("project_id") or request.args.get("project_id")
        project_id = int(project_id_str) if project_id_str and project_id_str != "None" and project_id_str.isdigit() else None
        if project_id is not None:
            project = db.session.get(Project, project_id)
            if not project or not has_edit_permission_project(project):
                return jsonify({"message": "没有权限上传到该项目"}), 403

        if not zip_file:
            if not files:
                return jsonify({"message": "缺少上传文件"}), 400
            if len(files) == 1:
                candidate = files[0]
                if not candidate:
                    return jsonify({"message": "缺少上传文件"}), 400
                if candidate.filename and candidate.filename.lower().endswith(".zip") and not zip_flag:
                    zip_file = candidate
                else:
                    data = candidate.read()
                    if not data:
                        return jsonify({"message": "上传文件为空"}), 400
                    zip_file = FileStorage(stream=io.BytesIO(data), filename="upload.zip", content_type="application/zip")
            else:
                valid_files = [f for f in files if f and f.filename]
                if not valid_files:
                    return jsonify({"message": "缺少上传文件"}), 400
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_ref:
                    for f in valid_files:
                        filename = f.filename or ""
                        normalized = filename.replace("--$--", "/").lstrip("/")
                        if not normalized:
                            continue
                        file_bytes = f.read()
                        zip_ref.writestr(normalized, file_bytes)
                zip_buffer.seek(0)
                zip_file = FileStorage(stream=zip_buffer, filename="upload.zip", content_type="application/zip")

        if not zip_file or not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
            return jsonify({"message": "必须是 .zip 文件"}), 400

        # 优化上传逻辑：同项目下同名检查
        # 如果指定了项目，则在项目内查找；如果未指定（项目ID为None），则在独立原型中查找
        query = Prototype.query.filter_by(name=name)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        else:
            query = query.filter_by(project_id=None)
        
        proto = query.first()

        if proto:
            # 如果存在同名原型，检查权限
            has_perm = has_edit_permission(proto)
            if not has_perm:
                # 检查是否拥有项目的编辑权限（如果原型属于项目）
                if project_id is not None:
                    proj = db.session.get(Project, project_id)
                    if proj and has_edit_permission_project(proj):
                        has_perm = True
            
            if not has_perm:
                owner_name = proto.owner.username if proto.owner else "未知用户"
                return jsonify({
                    "message": f"当前项目下已存在同名原型“{name}”（所有者：{owner_name}），您暂无权限修改。请联系管理员或修改原型名称。"
                }), 403

            # 有权限，执行更新逻辑
            proto.updater_id = current_user.id
            proto.updated_at = datetime.utcnow()
            project_present = "project_id" in request.form or "project_id" in request.args
            is_public_present = "is_public" in request.form or "is_public" in request.args
            access_password_present = "access_password" in request.form or "access_password" in request.args
            if project_present:
                proto.project_id = project_id
            if is_public_present:
                proto.is_public = is_public
            if access_password and access_password_present:
                proto.set_access_password(access_password)
            try:
                proto_path = deps.prototype_files_service.save_zip_and_extract(
                    proto_uuid=proto.uuid,
                    zip_file=zip_file,
                    overwrite=True,
                    progress_callback=report_extract_progress,
                )
            except ZipFileInvalidError:
                update_upload_progress("error", extract_loaded, extract_total, True, "ZIP文件已损坏或格式不正确")
                return jsonify({"message": "上传失败：ZIP文件已损坏或格式不正确"}), 400
            try:
                deps.prototype_service.process_ai(prototype_id=proto.id, proto_path=proto_path)
            except Exception:
                app.logger.exception("AI处理原型失败")
            db.session.commit()
            message = f'原型 "{name}" 更新成功！'
        else:
            # 不存在同名原型，创建新原型
            proto = Prototype(
                name=name,
                owner_id=user.id,
                updater_id=user.id,
                project_id=project_id,
                resource_type=resource_type,
                target_url=target_url,
                is_public=is_public,
            )
            if access_password:
                proto.set_access_password(access_password)
            db.session.add(proto)
            db.session.commit()
            try:
                proto_path = deps.prototype_files_service.save_zip_and_extract(
                    proto_uuid=proto.uuid,
                    zip_file=zip_file,
                    overwrite=False,
                    progress_callback=report_extract_progress,
                )
            except ZipFileInvalidError:
                db.session.delete(proto)
                db.session.commit()
                update_upload_progress("error", extract_loaded, extract_total, True, "ZIP文件已损坏或格式不正确")
                return jsonify({"message": "上传失败：ZIP文件已损坏或格式不正确"}), 400
            try:
                deps.prototype_service.process_ai(prototype_id=proto.id, proto_path=proto_path)
            except Exception:
                app.logger.exception("AI处理原型失败")
            db.session.commit()
            message = f'原型 "{name}" 创建成功！'

        update_upload_progress("done", extract_total, extract_total, True)
        return jsonify({"message": message, "id": proto.id, "short_id": deps.hashids.encode(proto.id)})

    @app.route("/api/upload/progress", methods=["GET"])
    @token_required
    def api_upload_progress() -> Response:
        upload_id = str(request.args.get("upload_id") or "").strip()
        if not upload_id:
            return jsonify({"message": "缺少 upload_id"}), 400
        data = upload_progress.get(upload_id)
        if not data:
            return jsonify({"stage": "unknown", "done": True}), 404
        clear_raw = str(request.args.get("clear") or "").lower()
        if data.get("done") and clear_raw in {"1", "true", "yes"}:
            upload_progress.pop(upload_id, None)
        return jsonify(data)

    @app.route("/api/ai/chat", methods=["POST"])
    def api_ai_chat() -> Response:
        data = request.get_json(silent=True) or {}
        short_id = str(data.get("short_id") or "").strip()
        page_path_raw = str(data.get("page_path") or "").strip()
        question = str(data.get("question") or "").strip()
        if not short_id or not question:
            return jsonify({"answer": default_ai_answer()}), 400

        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            return jsonify({"answer": default_ai_answer()}), 404

        proto = db.session.get(Prototype, prototype_id_tuple[0])
        if not proto:
            return jsonify({"answer": default_ai_answer()}), 404

        is_verified_public = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not is_verified_public:
            if not current_user.is_authenticated:
                return jsonify({"answer": default_ai_answer()}), 401
            if not has_view_permission(proto):
                return jsonify({"answer": default_ai_answer()}), 403

        page_path = urllib.parse.unquote(page_path_raw.split("#", 1)[0] or "").lstrip("/").strip() or "index.html"

        project_rules_text = deps.ai_service.load_project_rules_text()
        page_rule_text = deps.ai_service.get_page_rule_text(proto.id, page_path)
        try:
            need_chunks = os.environ.get("SILICONFLOW_API_KEY", "").strip() != "" and deps.ai_service.count_rule_chunks(
                proto.id, page_path
            ) == 0
            if not page_rule_text or need_chunks:
                deps.ai_service.ensure_page_indexed(proto.id, proto.uuid, page_path)
                page_rule_text = deps.ai_service.get_page_rule_text(proto.id, page_path)
        except Exception:
            pass

        knowledge_parts: list[str] = []
        if project_rules_text:
            knowledge_parts.append(f"【项目规则】\n{project_rules_text}")

        query_emb: list[float] = []
        try:
            query_emb = deps.ai_service.embed_text(question)
        except Exception:
            query_emb = []

        retrieved_chunks_current_page: list[str] = []
        retrieved_chunks_any_page: list[tuple[str, str]] = []
        keyword_rules_any_page: list[tuple[str, str]] = []
        if query_emb:
            try:
                retrieved_chunks_any_page = deps.ai_service.search_rule_chunks_in_prototype(proto.id, query_emb, top_k=6)
            except Exception:
                retrieved_chunks_any_page = []
            try:
                retrieved_chunks_current_page = deps.ai_service.search_rule_chunks(proto.id, page_path, query_emb, top_k=4)
            except Exception:
                retrieved_chunks_current_page = []

        if not retrieved_chunks_any_page:
            try:
                keyword_rules_any_page = deps.ai_service.search_page_rules_by_keywords(proto.id, question, top_k=3)
            except Exception:
                keyword_rules_any_page = []

        if retrieved_chunks_any_page:
            formatted = "\n\n".join([f"（来源：{p}）\n{t}" for p, t in retrieved_chunks_any_page])
            knowledge_parts.append("【原型规则（向量召回）】\n" + formatted)
        if retrieved_chunks_current_page:
            knowledge_parts.append("【当前页规则（向量召回）】\n" + "\n\n".join(retrieved_chunks_current_page))
        if keyword_rules_any_page and not retrieved_chunks_any_page:
            formatted = "\n\n".join([f"（来源：{p}）\n{t}" for p, t in keyword_rules_any_page])
            knowledge_parts.append("【原型规则（关键词匹配）】\n" + formatted)
        if page_rule_text and not retrieved_chunks_current_page:
            knowledge_parts.append("【原型页面规则】\n" + page_rule_text)

        knowledge_text = "\n\n".join([p for p in knowledge_parts if p.strip()])
        system_prompt = deps.ai_service.load_ai_system_prompt() or (
            """
            你是一个产品经理。你的核心职责是根据提供的知识库内容，准确回答用户（通常是开发同事）关于项目需求的问题。
请严格遵循以下步骤处理每一次查询：
1.  **理解问题**：仔细阅读用户提出的问题。
2.  **检索知识库**：在提供的《项目知识库》中查找与问题直接相关的信息。
3.  **判断与回答**：
    *   **如果知识库中有明确信息可以解答该问题**：请基于知识库内容，给出清晰、准确、简洁的回答。不要添加知识库中不存在的信息或你的个人推测。
    *   **如果知识库中没有相关信息，或信息不足以解答该问题**：请勿尝试猜测或自行推断答案。你应当统一回复：“关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。”
4.  **输出格式**：优先使用清晰的结构化表达（可使用 Markdown 列表与代码块），直接给出判断后的结果（要么是来自知识库的答案，要么是指定回复）。
请开始处理以下查询。
            """
        )
        if not os.environ.get("MAIN_AI_API_KEY", "").strip():
            if retrieved_chunks_any_page:
                return jsonify({"answer": "\n\n".join([t for _, t in retrieved_chunks_any_page])})
            if retrieved_chunks_current_page:
                return jsonify({"answer": "\n\n".join(retrieved_chunks_current_page)})
            if keyword_rules_any_page:
                return jsonify({"answer": "\n\n".join([t for _, t in keyword_rules_any_page])})
            if page_rule_text:
                return jsonify({"answer": page_rule_text})
            if project_rules_text:
                return jsonify({"answer": project_rules_text})
            return jsonify({"answer": default_ai_answer()})
        try:
            answer = deps.ai_service.call_main_ai(system_prompt=system_prompt, knowledge_text=knowledge_text, question=question)
        except Exception:
            answer = default_ai_answer()
        return jsonify({"answer": answer})

    @app.route("/api/ai/chat/stream", methods=["POST"])
    def api_ai_chat_stream() -> Response:
        data = request.get_json(silent=True) or {}
        short_id = str(data.get("short_id") or "").strip()
        page_path_raw = str(data.get("page_path") or "").strip()
        question = str(data.get("question") or "").strip()
        if not short_id or not question:
            return jsonify({"answer": default_ai_answer()}), 400

        prototype_id_tuple = deps.hashids.decode(short_id)
        if not prototype_id_tuple:
            return jsonify({"answer": default_ai_answer()}), 404

        proto = db.session.get(Prototype, prototype_id_tuple[0])
        if not proto:
            return jsonify({"answer": default_ai_answer()}), 404

        is_verified_public = bool(
            proto.is_public
            and (
                not proto.access_password
                or (session.get("verified_protos") and proto.id in session.get("verified_protos"))
            )
        )
        if not is_verified_public:
            if not current_user.is_authenticated:
                return jsonify({"answer": default_ai_answer()}), 401
            if not has_view_permission(proto):
                return jsonify({"answer": default_ai_answer()}), 403

        page_path = urllib.parse.unquote(page_path_raw.split("#", 1)[0] or "").lstrip("/").strip() or "index.html"

        project_rules_text = deps.ai_service.load_project_rules_text()
        page_rule_text = deps.ai_service.get_page_rule_text(proto.id, page_path)
        try:
            need_chunks = os.environ.get("SILICONFLOW_API_KEY", "").strip() != "" and deps.ai_service.count_rule_chunks(
                proto.id, page_path
            ) == 0
            if not page_rule_text or need_chunks:
                deps.ai_service.ensure_page_indexed(proto.id, proto.uuid, page_path)
                page_rule_text = deps.ai_service.get_page_rule_text(proto.id, page_path)
        except Exception:
            pass

        knowledge_parts: list[str] = []
        if project_rules_text:
            knowledge_parts.append(f"【项目规则】\n{project_rules_text}")

        query_emb: list[float] = []
        try:
            query_emb = deps.ai_service.embed_text(question)
        except Exception:
            query_emb = []

        retrieved_chunks_current_page: list[str] = []
        retrieved_chunks_any_page: list[tuple[str, str]] = []
        keyword_rules_any_page: list[tuple[str, str]] = []
        if query_emb:
            try:
                retrieved_chunks_any_page = deps.ai_service.search_rule_chunks_in_prototype(proto.id, query_emb, top_k=6)
            except Exception:
                retrieved_chunks_any_page = []
            try:
                retrieved_chunks_current_page = deps.ai_service.search_rule_chunks(proto.id, page_path, query_emb, top_k=4)
            except Exception:
                retrieved_chunks_current_page = []

        if not retrieved_chunks_any_page:
            try:
                keyword_rules_any_page = deps.ai_service.search_page_rules_by_keywords(proto.id, question, top_k=3)
            except Exception:
                keyword_rules_any_page = []

        if retrieved_chunks_any_page:
            formatted = "\n\n".join([f"（来源：{p}）\n{t}" for p, t in retrieved_chunks_any_page])
            knowledge_parts.append("【原型规则（向量召回）】\n" + formatted)
        if retrieved_chunks_current_page:
            knowledge_parts.append("【当前页规则（向量召回）】\n" + "\n\n".join(retrieved_chunks_current_page))
        if keyword_rules_any_page and not retrieved_chunks_any_page:
            formatted = "\n\n".join([f"（来源：{p}）\n{t}" for p, t in keyword_rules_any_page])
            knowledge_parts.append("【原型规则（关键词匹配）】\n" + formatted)
        if page_rule_text and not retrieved_chunks_current_page:
            knowledge_parts.append("【原型页面规则】\n" + page_rule_text)

        knowledge_text = "\n\n".join([p for p in knowledge_parts if p.strip()])
        system_prompt = deps.ai_service.load_ai_system_prompt() or (
            """
            你是一个产品经理。你的核心职责是根据提供的知识库内容，准确回答用户（通常是开发同事）关于项目需求的问题。
请严格遵循以下步骤处理每一次查询：
1.  **理解问题**：仔细阅读用户提出的问题。
2.  **检索知识库**：在提供的《项目知识库》中查找与问题直接相关的信息。
3.  **判断与回答**：
    *   **如果知识库中有明确信息可以解答该问题**：请基于知识库内容，给出清晰、准确、简洁的回答。不要添加知识库中不存在的信息或你的个人推测。
    *   **如果知识库中没有相关信息，或信息不足以解答该问题**：请勿尝试猜测或自行推断答案。你应当统一回复：“关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。”
4.  **输出格式**：优先使用清晰的结构化表达（可使用 Markdown 列表与代码块），直接给出判断后的结果（要么是来自知识库的答案，要么是指定回复）。
请开始处理以下查询。
            """
        )

        fallback_answer = ""
        if not os.environ.get("MAIN_AI_API_KEY", "").strip():
            if retrieved_chunks_any_page:
                fallback_answer = "\n\n".join([t for _, t in retrieved_chunks_any_page])
            elif retrieved_chunks_current_page:
                fallback_answer = "\n\n".join(retrieved_chunks_current_page)
            elif keyword_rules_any_page:
                fallback_answer = "\n\n".join([t for _, t in keyword_rules_any_page])
            elif page_rule_text:
                fallback_answer = page_rule_text
            elif project_rules_text:
                fallback_answer = project_rules_text
            else:
                fallback_answer = default_ai_answer()

        def gen() -> Any:
            yield "data: " + json.dumps({"type": "start"}, ensure_ascii=False) + "\n\n"
            if fallback_answer:
                for i in range(0, len(fallback_answer), 24):
                    yield "data: " + json.dumps({"delta": fallback_answer[i : i + 24]}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"done": True}, ensure_ascii=False) + "\n\n"
                return

            for delta in deps.ai_service.call_main_ai_stream(
                system_prompt=system_prompt, knowledge_text=knowledge_text, question=question
            ):
                if delta:
                    yield "data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"done": True}, ensure_ascii=False) + "\n\n"

        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return Response(gen(), mimetype="text/event-stream", headers=headers)

    @app.errorhandler(403)
    def forbidden(error: Exception) -> tuple[str, int]:
        return render_template("403.html"), 403

