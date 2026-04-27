"""WTForms 表单定义。"""

from __future__ import annotations

from flask import session
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FileField,
    IntegerField,
    MultipleFileField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.models import Project, User
from app.permissions import has_edit_permission_project


class LoginForm(FlaskForm):
    """登录表单。"""

    username = StringField("用户名", validators=[DataRequired()])
    password = PasswordField("密码", validators=[DataRequired()])
    captcha = IntegerField("验证码", validators=[DataRequired(message="请输入计算结果")])
    submit = SubmitField("登录")

    def validate_captcha(self, captcha: IntegerField) -> None:
        """校验验证码答案。"""

        correct_answer = session.get("captcha_answer")
        if correct_answer is None or captcha.data != correct_answer:
            raise ValidationError("计算结果错误！")


class AdminProfileForm(FlaskForm):
    """管理员个人资料表单。"""

    username = StringField("用户名", validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField("新密码 (留空则不修改)", validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField("确认新密码", validators=[EqualTo("password", message="两次输入的密码不一致")])
    submit = SubmitField("保存更改")

    def validate_username(self, username: StringField) -> None:
        """校验用户名唯一性。"""

        if username.data:
            user = User.query.filter(User.username == username.data, User.id != current_user.id).first()
            if user:
                raise ValidationError("该用户名已被使用，请选择其他用户名。")


class CreateUserForm(FlaskForm):
    """创建用户表单。"""

    username = StringField("用户名", validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField("新密码", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("确认密码", validators=[DataRequired(), EqualTo("password", message="两次输入的密码不一致")])
    submit = SubmitField("创建用户")


class EditUserForm(FlaskForm):
    """编辑用户表单。"""

    password = PasswordField("新密码 (留空则不修改)", validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField("确认新密码", validators=[EqualTo("password", message="两次输入的密码不一致")])
    submit = SubmitField("保存更改")


class GroupForm(FlaskForm):
    """用户组表单。"""

    name = StringField("用户组名称", validators=[DataRequired()])
    submit = SubmitField("保存")


class PublicPasswordForm(FlaskForm):
    """公开访问密码表单。"""

    password = PasswordField("请输入访问密码", validators=[DataRequired()])
    submit = SubmitField("确认")


class ProjectForm(FlaskForm):
    """项目表单。"""

    name = StringField("项目名称", validators=[DataRequired()])
    submit = SubmitField("保存")


class PrototypeUploadForm(FlaskForm):
    """原型上传表单。"""

    name = StringField("原型名称", validators=[DataRequired()])
    resource_type = RadioField(
        "资源类型",
        choices=[("axure", "Axure压缩包"), ("static", "普通HTML静态资源"), ("url", "外部链接")],
        default="axure",
        validators=[DataRequired()],
    )
    target_url = StringField("链接地址 (仅链接类型)", validators=[Optional()])
    rule_keywords = StringField(
        "原型说明关键词(元件名称)",
        validators=[Optional()],
        description="多个关键词用逗号分隔，默认：jiao_hu_gui_ze",
    )
    project_id = SelectField("所属项目 (可选)", coerce=int, validators=[Optional()])
    zip_file = FileField("压缩包 (ZIP)", validators=[Optional()])
    source_file = FileField("源文件 (.rp)", validators=[Optional()])
    attachment_files = MultipleFileField("附件 (可选)", validators=[Optional()])
    description = TextAreaField("备注", validators=[Optional()])
    is_public = BooleanField("公开访问 (无需登录)")
    access_password = StringField("访问密码 (公开访问时可选填)")
    submit = SubmitField("上传并保存")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.project_id.choices = [
            (p.id, p.name) for p in Project.query.order_by("name").all() if has_edit_permission_project(p)
        ]
        self.project_id.choices.insert(0, (0, "无项目 (独立原型)"))


class PrototypeEditForm(FlaskForm):
    """原型编辑表单。"""

    name = StringField("原型名称", validators=[DataRequired()])
    resource_type = RadioField(
        "资源类型",
        choices=[("axure", "Axure压缩包"), ("static", "普通HTML静态资源"), ("url", "外部链接")],
        validators=[DataRequired()],
    )
    target_url = StringField("链接地址 (仅链接类型)", validators=[Optional()])
    rule_keywords = StringField(
        "原型说明关键词(元件名称)",
        validators=[Optional()],
        description="多个关键词用逗号分隔，默认：jiao_hu_gui_ze",
    )
    project_id = SelectField("所属项目 (可选)", coerce=int, validators=[Optional()])
    attachment_files = MultipleFileField("更新附件 (可选)", validators=[Optional()])
    description = TextAreaField("备注")
    zip_file = FileField("更新压缩包 (可选)")
    source_file = FileField("更新源文件 (可选)")
    is_public = BooleanField("公开访问 (无需登录)")
    access_password = StringField("访问密码 (公开访问时可选填)")
    submit = SubmitField("保存更改")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.project_id.choices = [(p.id, p.name) for p in Project.query.order_by("name").all()]
        self.project_id.choices.insert(0, (0, "无项目 (独立原型)"))

