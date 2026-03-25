"""网络相关工具函数。"""

from __future__ import annotations

from flask import Request


def get_remote_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址。
    优先从 X-Forwarded-For 获取，其次是 X-Real-IP，最后是 remote_addr。
    """
    if "X-Forwarded-For" in request.headers:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2>
        # 通常第一个 IP 是真实的客户端 IP
        x_forwarded_for = request.headers["X-Forwarded-For"]
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

    if "X-Real-IP" in request.headers:
        return request.headers["X-Real-IP"]

    return request.remote_addr or "127.0.0.1"
