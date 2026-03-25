"""应用包导出。"""

from __future__ import annotations

from flask import Flask

from app.app_factory import create_app

app: Flask = create_app()
