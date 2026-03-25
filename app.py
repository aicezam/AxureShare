"""项目启动入口。"""

from __future__ import annotations

from flask import Flask

from app.app_factory import create_app

app: Flask = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=7855)

