"""JSON HTTP 请求工具。"""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def http_json_post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout_sec: int = 60) -> dict[str, Any]:
    """发起 JSON POST 请求并解析返回为 dict。"""

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw)
        except Exception:
            return {"_raw": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"_raw": raw}

