"""AI 规则索引与对话服务。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator

from app.utils.html_rules import extract_rule_text_from_html, inject_ai_widget_into_html, iter_html_files
from app.utils.http_json import http_json_post
from app.utils.path_security import is_within_directory
from app.utils.text_chunking import chunk_text
from app.utils.text_files import read_text_file
from app.utils.vector_math import cosine_similarity


def _default_answer() -> str:
    return "关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。"


def _extract_keywords(question: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", question or "")
    stop = {
        "什么",
        "怎么",
        "如何",
        "是否",
        "规则",
        "页面",
        "这个",
        "那个",
        "哪些",
        "多少",
        "请问",
        "以及",
        "还有",
        "和",
        "与",
        "的",
        "是",
        "在",
        "我",
        "你",
        "他",
        "她",
        "它",
    }
    uniq: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        tt = t.strip()
        if not tt or tt in stop:
            continue
        if tt not in seen:
            uniq.append(tt)
            seen.add(tt)
    return uniq[:12]


def _keyword_score(text: str, keywords: list[str]) -> int:
    if not text or not keywords:
        return 0
    s = 0
    lower = text.lower()
    for kw in keywords:
        if not kw:
            continue
        if kw.lower() in lower:
            s += 1
    return s


def _chunk_for_stream(text: str, chunk_size: int = 24) -> Iterator[str]:
    if not text:
        return
    i = 0
    n = len(text)
    while i < n:
        yield text[i : i + chunk_size]
        i += chunk_size


@dataclass(frozen=True)
class AiService:
    """AI 相关能力集合。"""

    base_dir: str
    prototypes_folder: str
    instance_folder: str

    def init_storage(self) -> None:
        """初始化 AI SQLite 存储。"""

        os.makedirs(self.instance_folder, exist_ok=True)
        db_path = self._db_path()

        def create_tables(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_page_rule (
                    prototype_id INTEGER NOT NULL,
                    page_path TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (prototype_id, page_path)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_rule_chunk (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prototype_id INTEGER NOT NULL,
                    page_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    rule_text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (prototype_id, page_path, chunk_index)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_rule_chunk_proto_page ON ai_rule_chunk(prototype_id, page_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_rule_chunk_proto ON ai_rule_chunk(prototype_id)")
            conn.commit()

        needs_reset = False
        try:
            with self._connect() as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                if row and str(row[0]).lower() != "ok":
                    needs_reset = True
        except (sqlite3.DatabaseError, PermissionError, OSError):
            needs_reset = True

        if needs_reset:
            new_db_path = ""
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except (PermissionError, OSError):
                    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    new_db_path = os.path.join(self.instance_folder, f"ai_fallback_{stamp}.db")
            target_path = new_db_path or self._db_path()
            try:
                with sqlite3.connect(target_path) as conn:
                    create_tables(conn)
            except sqlite3.DatabaseError:
                stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                fallback_path = os.path.join(self.instance_folder, f"ai_fallback_{stamp}.db")
                with sqlite3.connect(fallback_path) as conn:
                    create_tables(conn)

        with self._connect() as conn:
            create_tables(conn)

    def process_prototype(self, prototype_id: int, proto_root_dir: str) -> None:
        """对整个原型目录进行规则提取、向量索引与挂件注入。"""

        # 获取原型配置的关键词
        keywords = ["jiao_hu_gui_ze"]
        proto_resource_type = "axure"
        try:
            from app.extensions import db
            from app.models import Prototype

            proto = db.session.get(Prototype, prototype_id)
            if proto and proto.rule_keywords:
                loaded = json.loads(proto.rule_keywords)
                if isinstance(loaded, list):
                    keywords = loaded
            if proto and proto.resource_type:
                proto_resource_type = str(proto.resource_type)
        except Exception:
            pass

        for fp in iter_html_files(proto_root_dir):
            html = read_text_file(fp)
            if not html:
                continue

            if proto_resource_type == "axure":
                try:
                    injected = inject_ai_widget_into_html(html)
                    if injected != html:
                        with open(fp, "w", encoding="utf-8") as f:
                            f.write(injected)
                except Exception:
                    pass

            rule_text = extract_rule_text_from_html(html, labels=keywords)
            if not rule_text:
                continue

            page_path = os.path.relpath(fp, proto_root_dir).replace("\\", "/")
            self.save_page_rule(prototype_id, page_path, rule_text)

            chunks = chunk_text(rule_text)
            if not chunks:
                continue

            pairs: list[tuple[str, list[float]]] = []
            for c in chunks:
                try:
                    emb = self.embed_text(c)
                except Exception:
                    emb = []
                if emb:
                    pairs.append((c, emb))
            if pairs:
                self.replace_rule_chunks(
                    prototype_id=prototype_id,
                    page_path=page_path,
                    chunks=[p[0] for p in pairs],
                    embeddings=[p[1] for p in pairs],
                )

    def ensure_page_indexed(self, prototype_id: int, proto_uuid: str, page_path: str) -> None:
        """按页面路径补齐规则与索引。"""

        proto_root_dir = os.path.join(self.prototypes_folder, proto_uuid)
        root_real = os.path.realpath(proto_root_dir)
        decoded = urllib.parse.unquote(page_path or "")
        rel = decoded.replace("\\", "/").lstrip("/").strip()
        if not rel:
            return

        abs_path = os.path.realpath(os.path.join(proto_root_dir, rel))
        if not is_within_directory(root_real, abs_path) or not os.path.exists(abs_path):
            return

        html = read_text_file(abs_path)
        if not html:
            return
        rule_text = extract_rule_text_from_html(html, label="jiao_hu_gui_ze")
        if not rule_text:
            return

        self.save_page_rule(prototype_id, rel, rule_text)
        if self.count_rule_chunks(prototype_id, rel) > 0:
            return

        chunks = chunk_text(rule_text)
        if not chunks:
            return

        pairs: list[tuple[str, list[float]]] = []
        for c in chunks:
            emb = self.embed_text(c)
            if emb:
                pairs.append((c, emb))
        if pairs:
            self.replace_rule_chunks(
                prototype_id=prototype_id,
                page_path=rel,
                chunks=[p[0] for p in pairs],
                embeddings=[p[1] for p in pairs],
            )

    def get_page_rule_text(self, prototype_id: int, page_path: str) -> str:
        """读取页面规则文本。"""

        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT rule_text FROM ai_page_rule WHERE prototype_id=? AND page_path=?",
                    (prototype_id, page_path),
                ).fetchone()
                if row:
                    return str(row["rule_text"])
        except sqlite3.DatabaseError:
            return ""
        return ""

    def count_rule_chunks(self, prototype_id: int, page_path: str) -> int:
        """统计页面规则块数量。"""

        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(1) AS c FROM ai_rule_chunk WHERE prototype_id=? AND page_path=?",
                    (prototype_id, page_path),
                ).fetchone()
                if not row:
                    return 0
                try:
                    return int(row["c"])
                except Exception:
                    return 0
        except sqlite3.DatabaseError:
            return 0

    def search_rule_chunks(self, prototype_id: int, page_path: str, query_embedding: list[float], top_k: int = 5) -> list[str]:
        """按向量相似度检索页面规则块。"""

        if not query_embedding:
            return []
        candidates: list[tuple[float, str]] = []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT rule_text, embedding_json FROM ai_rule_chunk WHERE prototype_id=? AND page_path=?",
                    (prototype_id, page_path),
                ).fetchall()
        except sqlite3.DatabaseError:
            return []
        for r in rows:
            try:
                emb = json.loads(r["embedding_json"])
                if not isinstance(emb, list):
                    continue
                emb_vec = [float(x) for x in emb]
            except Exception:
                continue
            score = cosine_similarity(query_embedding, emb_vec)
            if score > -1.0:
                candidates.append((score, str(r["rule_text"])))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in candidates[:top_k]]

    def search_rule_chunks_in_prototype(
        self, prototype_id: int, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[str, str]]:
        if not query_embedding:
            return []
        candidates: list[tuple[float, str, str]] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT page_path, rule_text, embedding_json FROM ai_rule_chunk WHERE prototype_id=?",
                (prototype_id,),
            ).fetchall()
        for r in rows:
            try:
                emb = json.loads(r["embedding_json"])
                if not isinstance(emb, list):
                    continue
                emb_vec = [float(x) for x in emb]
            except Exception:
                continue
            score = cosine_similarity(query_embedding, emb_vec)
            if score > -1.0:
                candidates.append((score, str(r["page_path"]), str(r["rule_text"])))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [(p, t) for _, p, t in candidates[:top_k]]

    def search_page_rules_by_keywords(self, prototype_id: int, question: str, top_k: int = 5) -> list[tuple[str, str]]:
        keywords = _extract_keywords(question)
        if not keywords:
            return []
        candidates: list[tuple[int, str, str]] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT page_path, rule_text FROM ai_page_rule WHERE prototype_id=?",
                (prototype_id,),
            ).fetchall()
        for r in rows:
            page_path = str(r["page_path"])
            rule_text = str(r["rule_text"])
            score = _keyword_score(rule_text, keywords)
            if score > 0:
                candidates.append((score, page_path, rule_text))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [(p, t) for _, p, t in candidates[:top_k]]

    def load_ai_system_prompt(self) -> str:
        """加载 AI 系统提示词。"""

        return read_text_file(os.path.join(self.base_dir, "AI相关文档", "提示词.md")).strip()

    def load_project_rules_text(self) -> str:
        """加载项目规则文本。"""

        return read_text_file(os.path.join(self.base_dir, ".trae", "rules", "project_rules.md")).strip()

    def embed_text(self, text: str) -> list[float]:
        """调用向量模型获取文本 embedding。"""

        api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
        if not api_key:
            return []
        base_url = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
        model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3").strip() or "BAAI/bge-m3"
        url = f"{base_url}/embeddings"
        resp = http_json_post(
            url=url,
            headers={"Authorization": f"Bearer {api_key}"},
            payload={"model": model, "input": text, "encoding_format": "float"},
            timeout_sec=60,
        )
        data = resp.get("data")
        if isinstance(data, list) and data:
            emb = data[0].get("embedding")
            if isinstance(emb, list):
                try:
                    return [float(x) for x in emb]
                except Exception:
                    return []
        return []

    def call_main_ai(self, system_prompt: str, knowledge_text: str, question: str) -> str:
        """调用主模型进行回答。"""

        api_key = os.environ.get("MAIN_AI_API_KEY", "").strip()
        if not api_key:
            return _default_answer()
        base_url = os.environ.get("MAIN_AI_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
        model = (os.environ.get("MAIN_AI_MODEL") or os.environ.get("AIN_AI_MODEL") or "mimo-v2-flash").strip() or "mimo-v2-flash"
        url = f"{base_url}/chat/completions"
        user_content = f"《项目知识库》：\n{knowledge_text}\n\n用户问题：\n{question}"
        resp = http_json_post(
            url=url,
            headers={"Authorization": f"Bearer {api_key}"},
            payload={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.2,
            },
            timeout_sec=90,
        )
        try:
            choices = resp.get("choices")
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        except Exception:
            pass
        return _default_answer()

    def call_main_ai_stream(self, system_prompt: str, knowledge_text: str, question: str) -> Iterator[str]:
        """以流式方式调用主模型进行回答。"""

        api_key = os.environ.get("MAIN_AI_API_KEY", "").strip()
        if not api_key:
            yield from _chunk_for_stream(_default_answer())
            return

        base_url = os.environ.get("MAIN_AI_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
        model = (os.environ.get("MAIN_AI_MODEL") or os.environ.get("AIN_AI_MODEL") or "mimo-v2-flash").strip() or "mimo-v2-flash"
        url = f"{base_url}/chat/completions"
        user_content = f"《项目知识库》：\n{knowledge_text}\n\n用户问题：\n{question}"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "stream": True,
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                content_type = str(resp.headers.get("Content-Type") or "")
                is_sse = "text/event-stream" in content_type.lower()
                if not is_sse:
                    raw = resp.read().decode("utf-8", errors="ignore")
                    try:
                        parsed = json.loads(raw)
                    except Exception:
                        yield from _chunk_for_stream(raw.strip() or _default_answer())
                        return
                    try:
                        choices = parsed.get("choices")
                        if isinstance(choices, list) and choices:
                            msg = choices[0].get("message") or {}
                            content = msg.get("content")
                            if isinstance(content, str) and content.strip():
                                yield from _chunk_for_stream(content.strip())
                                return
                    except Exception:
                        pass
                    yield from _chunk_for_stream(_default_answer())
                    return

                while True:
                    line = resp.readline()
                    if not line:
                        break
                    s = line.decode("utf-8", errors="ignore").strip()
                    if not s or not s.startswith("data:"):
                        continue
                    data_str = s[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except Exception:
                        continue
                    try:
                        choices = obj.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        c0 = choices[0] or {}
                        delta_obj = c0.get("delta") or {}
                        delta_text: str | None = None
                        if isinstance(delta_obj, dict):
                            dt = delta_obj.get("content")
                            if isinstance(dt, str):
                                delta_text = dt
                        if not delta_text:
                            txt = c0.get("text")
                            if isinstance(txt, str):
                                delta_text = txt
                        if delta_text:
                            yield delta_text
                    except Exception:
                        continue
        except Exception:
            yield from _chunk_for_stream(_default_answer())

    def save_page_rule(self, prototype_id: int, page_path: str, rule_text: str) -> None:
        """保存页面规则文本。"""

        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_page_rule(prototype_id, page_path, rule_text, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(prototype_id, page_path) DO UPDATE SET rule_text=excluded.rule_text, updated_at=excluded.updated_at
                """,
                (prototype_id, page_path, rule_text, now),
            )
            conn.commit()

    def replace_rule_chunks(self, prototype_id: int, page_path: str, chunks: list[str], embeddings: list[list[float]]) -> None:
        """替换页面规则的向量块索引。"""

        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM ai_rule_chunk WHERE prototype_id=? AND page_path=?", (prototype_id, page_path))
            for idx, (chunk_text_item, emb) in enumerate(zip(chunks, embeddings)):
                conn.execute(
                    """
                    INSERT INTO ai_rule_chunk(prototype_id, page_path, chunk_index, rule_text, embedding_json, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prototype_id,
                        page_path,
                        idx,
                        chunk_text_item,
                        json.dumps(emb, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path())
        conn.row_factory = sqlite3.Row
        return conn

    def _db_path(self) -> str:
        candidates: list[str] = []
        fb = os.path.join(self.instance_folder, "ai_fallback.db")
        if os.path.exists(fb):
            candidates.append(fb)
        try:
            for name in os.listdir(self.instance_folder):
                if name.startswith("ai_fallback_") and name.endswith(".db"):
                    candidates.append(os.path.join(self.instance_folder, name))
        except Exception:
            candidates = candidates
        if candidates:
            return max(candidates, key=lambda p: os.path.getmtime(p))
        return os.path.join(self.instance_folder, "ai.db")
