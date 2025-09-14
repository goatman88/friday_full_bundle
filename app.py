# app.py
from __future__ import annotations
import os, json
import datetime as dt
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from sqlalchemy import create_engine, text, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

APP_TOKEN = os.getenv("APP_TOKEN") or os.getenv("API_TOKEN") or "dev_token"

def normalize_db_url(raw: str | None) -> str:
    """
    Render often provides `postgres://...`. SQLAlchemy wants `postgresql+psycopg2://`.
    We also coerce any `postgresql://` (no driver) to `postgresql+psycopg2://`.
    """
    if not raw or not raw.strip():
        return "sqlite:///friday.db"
    url = raw.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # If user pasted a plain postgresql:// (no +driver), pin to psycopg2 driver
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

DATABASE_URL = normalize_db_url(os.getenv("DATABASE_URL"))

def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String(64), primary_key=True)
    title = Column(String(500), nullable=False)
    text = Column(Text, nullable=False)
    source = Column(String(120))
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

def init_db() -> None:
    Base.metadata.create_all(engine)
    if is_postgres():
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_fts
                ON documents
                USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')));
            """))

# Initialize schema at import time (safe, idempotent)
try:
    init_db()
except SQLAlchemyError as e:
    # Don’t crash the import; surface error via /health and logs
    print("DB init error:", e)

def routes_list(app) -> List[str]:
    return sorted(str(r) for r in app.url_map.iter_rules())

def auth_ok(req) -> bool:
    auth = req.headers.get("Authorization", "")
    return auth.startswith("Bearer ") and auth.split(" ", 1)[1].strip() != ""

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_port=1, x_proto=1, x_host=1)

@app.get("/")
def root():
    return jsonify({"message": "Friday backend is running", "ok": True, "routes": routes_list(app)})

@app.get("/__routes")
def list_routes():
    return jsonify(routes_list(app))

@app.get("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(dt.datetime.utcnow().timestamp() * 1_000_000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.sys.version.split(" ")[0],
        "db": DATABASE_URL.split("://", 1)[0]
    })

@app.get("/health")
def health():
    # basic DB probe
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False
    return jsonify({"ok": True, "status": "running", "db_ok": db_ok}), 200

@app.get("/ping")
def ping():
    return "pong", 200

# ---------- RAG API ----------

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

    doc_id = f"doc_{abs(hash(title + text_)) % (10**10)}"
    with SessionLocal() as s:
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
    topk = min(max(int(body.get("topk") or 3), 1), 10)
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    contexts: List[Dict[str, Any]] = []
    with SessionLocal() as s:
        if is_postgres():
            rows = s.execute(text("""
                SELECT id, title, text, source,
                       ts_rank_cd(
                         to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')),
                         plainto_tsquery('english', :q)
                       ) AS score
                FROM documents
                WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(text,'')) @@ plainto_tsquery('english', :q)
                ORDER BY score DESC, created_at DESC
                LIMIT :k
            """), {"q": query, "k": topk}).mappings().all()
        else:
            rows = s.execute(text("""
                SELECT id, title, text, source, 0.0 AS score
                FROM documents
                WHERE title LIKE :pat OR text LIKE :pat
                ORDER BY created_at DESC
                LIMIT :k
            """), {"pat": f"%{query}%", "k": topk}).mappings().all()

        for r in rows:
            preview = r["text"][:240] + ("…" if len(r["text"]) > 240 else "")
            contexts.append({
                "id": r["id"], "title": r["title"], "preview": preview,
                "score": float(r.get("score", 0.0)), "source": r.get("source")
            })

    answer = contexts[0]["preview"] if contexts else "I couldn’t find anything relevant."
    return jsonify({"ok": True, "answer": answer, "contexts": contexts}), 200

@app.get("/demo")
def demo_redirect():
    return send_from_directory("static", "chat.html")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)



























































