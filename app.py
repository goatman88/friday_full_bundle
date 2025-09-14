# src/app.py
from __future__ import annotations

import os
import re
import socket
import time
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import (
    create_engine,
    text as sql_text,
    String,
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, Session
from sqlalchemy.exc import OperationalError, ProgrammingError


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def normalize_db_url(raw: str | None) -> str:
    """
    Render exposes DATABASE_URL as either:
      - postgres://user:pass@host:port/db
      - postgresql://user:pass@host:port/db
    SQLAlchemy + psycopg2 expects 'postgresql+psycopg2://...'
    """
    if not raw or not raw.strip():
        # Local dev fallback (file lives beside this module)
        db_path = os.path.join(os.path.dirname(__file__), "local.db")
        return f"sqlite:///{db_path}"
    url = raw.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


API_TOKEN = os.getenv("API_TOKEN", "").strip()
DB_URL = normalize_db_url(os.getenv("DATABASE_URL"))
SERVICE_NAME = os.getenv("RENDER_SERVICE_NAME", "friday")
STARTED_AT = time.time()


# ---------------------------------------------------------------------------
# Database setup (SQLAlchemy 2.0 style)
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(64), default="upload")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


engine = create_engine(
    DB_URL,
    pool_pre_ping=True,           # heal stale connections
    pool_recycle=300,             # recycle periodically (Render idles)
    future=True,
)

def init_db() -> None:
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

# Create tables at import time (safe on Render; CREATE TABLE IF NOT EXISTS)
try:
    init_db()
except Exception as e:
    # Don’t crash boot if DB isn’t reachable yet (first cold start).
    app.logger.warning(f"DB init warning: {e}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def ok(data: Dict[str, Any] | List[Any] | None = None, status: int = 200):
    payload: Dict[str, Any] = {"ok": True}
    if isinstance(data, dict):
        payload.update(data)
    elif data is not None:
        payload["data"] = data
    return jsonify(payload), status


def err(message: str, status: int = 400, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status


def require_bearer() -> str | None:
    """
    Returns error response if unauthorized; otherwise returns None.
    """
    if not API_TOKEN:
        return "Server missing API_TOKEN (set env var)"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "Missing Authorization: Bearer <token>"
    token = auth.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        return "Invalid token"
    return None


def simple_keyword_score(query: str, text: str) -> float:
    """
    Ultra-light "retrieval" scoring: score by keyword overlap (case-insensitive).
    Not a vector search, but good enough to prove the path end-to-end.
    """
    q_terms = {t for t in re.findall(r"[A-Za-z0-9]+", query.lower()) if len(t) > 2}
    if not q_terms:
        return 0.0
    t_terms = {t for t in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(t) > 2}
    if not t_terms:
        return 0.0
    inter = q_terms.intersection(t_terms)
    return round(len(inter) / len(q_terms), 4)


# ---------------------------------------------------------------------------
# “Public” routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return ok({
        "message": "Friday backend is running",
        "status": "running",
        "routes": [
            "/", "/__routes", "/__whoami",
            "/api/rag/index", "/api/rag/query",
            "/health", "/ping", "/static/<path:filename>"
        ],
    })


@app.get("/__routes")
def list_routes():
    routes = sorted({rule.rule for rule in app.url_map.iter_rules()})
    return jsonify(routes)


@app.get("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(STARTED_AT * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}",
        "service": SERVICE_NAME,
        "host": socket.gethostname(),
    })


@app.get("/health")
def health():
    # Try a trivial DB roundtrip so health reflects storage readiness
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        storage = "ok"
    except Exception as e:
        storage = f"degraded: {type(e).__name__}"
    return ok({"status": "running", "storage": storage})


@app.get("/ping")
def ping():
    return ok({"pong": True, "uptime_s": round(time.time() - STARTED_AT, 1)})


@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


# ---------------------------------------------------------------------------
# RAG-ish API
# ---------------------------------------------------------------------------

@app.post("/api/rag/index")
def rag_index():
    unauthorized = require_bearer()
    if unauthorized:
        return err(unauthorized, status=401)

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    text_val = (body.get("text") or "").strip()
    source = (body.get("source") or "upload").strip()[:64]

    if not text_val:
        return err("Field 'text' is required")

    try:
        with Session(engine) as s:
            doc = Document(title=title[:255], text=text_val, source=source)
            s.add(doc)
            s.commit()
            return ok({"indexed": [{"id": doc.id, "title": doc.title}]})
    except (OperationalError, ProgrammingError) as e:
        return err("Storage error", 500, detail=str(e)[:200])


@app.post("/api/rag/query")
def rag_query():
    unauthorized = require_bearer()
    if unauthorized:
        return err(unauthorized, status=401)

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or 3)

    if not query:
        return err("Field 'query' is required")

    # Naive retrieval: scan a limited window of most recent docs and score
    try:
        with Session(engine) as s:
            docs: List[Document] = (
                s.query(Document)
                 .order_by(Document.id.desc())
                 .limit(200)
                 .all()
            )

        scored = []
        for d in docs:
            score = simple_keyword_score(query, d.text or "")
            if score > 0:
                scored.append({
                    "id": d.id,
                    "title": d.title,
                    "score": score,
                    "preview": (d.text[:180] + "…") if d.text and len(d.text) > 180 else (d.text or "")
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        contexts = scored[:max(1, min(10, topk))]

        # Trivial "answer": if a top context exists, reuse its preview;
        # otherwise return a generic message. (Hook your LLM here later.)
        if contexts:
            answer = contexts[0]["preview"]
        else:
            answer = "No matching context found yet. Try indexing relevant documents first."

        return ok({"answer": answer, "contexts": contexts})
    except Exception as e:
        return err("Query failed", 500, detail=str(e)[:200])


# ---------------------------------------------------------------------------
# Error handlers (JSON everywhere)
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_):
    return err("Not Found", 404)

@app.errorhandler(405)
def method_not_allowed(_):
    return err("Method Not Allowed", 405)

@app.errorhandler(Exception)
def on_error(ex: Exception):
    # Don’t leak internals in prod; include type and short detail
    return err("Internal Server Error", 500, type=type(ex).__name__, detail=str(ex)[:240])


# ---------------------------------------------------------------------------
# Local dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Local dev: python -m flask run OR just python src/app.py
    # Flask dev server binds to 0.0.0.0 for convenience in containers.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=bool(os.getenv("DEBUG")))






























































