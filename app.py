# app.py
from __future__ import annotations
import os
import json
import datetime as dt
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from sqlalchemy import (
    create_engine, text, Column, String, Text, DateTime, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError, ProgrammingError

APP_TOKEN = os.getenv("APP_TOKEN") or os.getenv("API_TOKEN") or "dev_token"

DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. from Render Postgres
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy prefers postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback to local SQLite if no DATABASE_URL provided
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///friday.db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String(64), primary_key=True)          # simple string id
    title = Column(String(500), nullable=False)
    text = Column(Text, nullable=False)
    source = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")

def init_db() -> None:
    """Create tables & FTS index (Postgres), no-op if exists."""
    Base.metadata.create_all(engine)
    if _is_postgres():
        with engine.begin() as conn:
            # Optional helpful extensions for FTS quality/ranking:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            # Materialized TSVECTOR column via generated column (PG >=12),
            # or create an index on the expression directly:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_fts
                ON documents
                USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')));
            """))

init_db()

def routes_list() -> List[str]:
    rts = []
    for rule in app.url_map.iter_rules():
        rts.append(str(rule))
    return sorted(rts)

def auth_ok(req) -> bool:
    auth = req.headers.get("Authorization", "")
    return auth.startswith("Bearer ") and auth.split(" ", 1)[1].strip() != ""

def bearer_token(req) -> str:
    auth = req.headers.get("Authorization", "")
    return auth.split(" ", 1)[1].strip() if auth.startswith("Bearer ") else ""

app = Flask(__name__, static_folder="static", static_url_path="/static")
# Make Flask happy behind Render's proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_port=1, x_proto=1, x_host=1)

@app.get("/")
def root():
    return jsonify({
        "message": "Friday backend is running",
        "ok": True,
        "routes": routes_list()
    })

@app.get("/__routes")
def list_routes():
    return jsonify(routes_list())

@app.get("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(dt.datetime.utcnow().timestamp() * 1000000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.sys.version.split(" ")[0],
    })

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.get("/ping")
def ping():
    return "pong", 200

# ----------- RAG: index & query (DB-backed) ----------------

@app.post("/api/rag/index")
def rag_index():
    if not auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    text_ = (body.get("text") or "").strip()
    source = (body.get("source") or "faq").strip()

    if not title or not text_:
        return jsonify({"ok": False, "error": "title and text are required"}), 400

    # Simple deterministic id (could be uuid)
    doc_id = f"doc_{abs(hash(title + text_)) % (10**10)}"

    with SessionLocal() as s:
        # upsert-ish: delete then insert (safe & simple)
        s.execute(text("DELETE FROM documents WHERE id=:id"), {"id": doc_id})
        s.add(Document(id=doc_id, title=title, text=text_, source=source))
        s.commit()

    return jsonify({"ok": True, "indexed": [{"id": doc_id, "title": title}]}), 200


@app.post("/api/rag/query")
def rag_query():
    if not auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or 3)
    topk = min(max(topk, 1), 10)

    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    contexts: List[Dict[str, Any]] = []

    with SessionLocal() as s:
        if _is_postgres():
            # Use Postgres full-text search with ranking
            sql = text("""
                SELECT id, title, text, source,
                       ts_rank_cd(
                         to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')),
                         plainto_tsquery('english', :q)
                       ) AS score
                FROM documents
                WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')) @@ plainto_tsquery('english', :q)
                ORDER BY score DESC, created_at DESC
                LIMIT :k
            """)
            rows = s.execute(sql, {"q": query, "k": topk}).mappings().all()
        else:
            # SQLite fallback (basic, but works)
            sql = text("""
                SELECT id, title, text, source, 0.0 AS score
                FROM documents
                WHERE title LIKE :pat OR text LIKE :pat
                ORDER BY created_at DESC
                LIMIT :k
            """)
            rows = s.execute(sql, {"pat": f"%{query}%", "k": topk}).mappings().all()

        for r in rows:
            preview = r["text"]
            if len(preview) > 240:
                preview = preview[:240] + "…"
            contexts.append({
                "id": r["id"],
                "title": r["title"],
                "preview": preview,
                "score": float(r.get("score", 0.0)),
                "source": r.get("source")
            })

    # Dumb demo “answer”: pick best snippet if any
    answer = "I couldn’t find anything relevant."
    if contexts:
        answer = contexts[0]["preview"]

    return jsonify({"ok": True, "answer": answer, "contexts": contexts}), 200

# Serve the demo client
@app.get("/demo")
def demo_redirect():
    return send_from_directory("static", "chat.html")

# Render/Waitress entrypoint:
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


























































