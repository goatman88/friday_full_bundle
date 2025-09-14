import os
import time
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ---------- Config ----------
API_TOKEN = os.getenv("API_TOKEN", "").strip()
# Choose the driver: "psycopg2" (matches your requirements) or "psycopg" (v3)
DB_DIALECT = "psycopg2"   # set to "psycopg" if you add psycopg[binary] to requirements

# Render Managed Postgres usually exposes DATABASE_URL
RAW_DB_URL = os.getenv("DATABASE_URL", "").strip()

def _normalize_db_url(raw: str) -> str:
    """
    Render sometimes provides URLs like 'postgres://...' which SQLAlchemy treats as deprecated.
    Normalize to 'postgresql+<driver>://...'.
    """
    if not raw:
        # Dev fallback so the service can still boot without Postgres.
        return "sqlite:///friday.db"
    # swap postgres:// with postgresql://
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    # inject explicit driver
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", f"postgresql+{DB_DIALECT}://", 1)
    return raw

DB_URL = _normalize_db_url(RAW_DB_URL)

# ---------- App ----------
app = Flask(__name__, static_folder="static")
CORS(app)

# ---------- Database (SQLAlchemy 2.0 style) ----------
from sqlalchemy import (
    create_engine, text, Integer, String, Text, DateTime
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def init_db() -> None:
    Base.metadata.create_all(engine)

# Create tables on cold start (safe/no-op when already created)
try:
    init_db()
except Exception as e:
    # Don't crash the process; let /health report the error
    app.logger.warning("DB init warning: %s", e)

# ---------- Helpers ----------
def auth_ok(req) -> bool:
    if not API_TOKEN:
        # If no token configured, allow all (useful during setup).
        return True
    auth = req.headers.get("Authorization", "")
    return auth == f"Bearer {API_TOKEN}"

def list_routes() -> List[str]:
    routes = []
    for rule in app.url_map.iter_rules():
        # Skip static rules if you don't want to show them.
        routes.append(str(rule))
    return sorted(routes)

def simple_score(query: str, text_: str) -> float:
    """Very light signal: overlap ratio."""
    q = query.lower().split()
    t = text_.lower()
    hits = sum(1 for w in q if w in t)
    return round(hits / (len(q) or 1), 4)

# ---------- Public routes ----------
@app.get("/")
def root():
    return jsonify({
        "message": "Friday backend is running",
        "ok": True,
        "routes": list_routes(),
    })

@app.get("/__routes")
def routes():
    return jsonify(list_routes())

@app.get("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(time.time() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip() or "unknown",
    })

@app.get("/health")
def health():
    # Basic DB check
    db_ok = True
    db_err = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_err = str(e)
    return jsonify({"ok": True, "status": "running", "db_ok": db_ok, "db_error": db_err})

@app.get("/ping")
def ping():
    return jsonify({"pong": True, "ts": int(time.time())})

@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)

# ---------- RAG-ish endpoints backed by Postgres ----------
@app.post("/api/rag/index")
def rag_index():
    if not auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()[:255]
    text_content = (body.get("text") or "").strip()
    source = (body.get("source") or "user").strip()[:64] or "user"

    if not text_content:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400

    with SessionLocal() as s:
        doc = Document(title=title or "Untitled", text=text_content, source=source)
        s.add(doc)
        s.commit()
        s.refresh(doc)

    return jsonify({
        "ok": True,
        "indexed": [{"id": f"doc_{doc.id}", "title": doc.title}]
    })

@app.post("/api/rag/query")
def rag_query():
    if not auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or 3)
    topk = max(1, min(topk, 20))

    if not query:
        return jsonify({"ok": False, "error": "Missing 'query'"}), 400

    # simplest “retrieval”: ILIKE filter then score in Python
    with SessionLocal() as s:
        q = f"%{query}%"
        docs: List[Document] = list(
            s.query(Document)
             .filter((Document.text.ilike(q)) | (Document.title.ilike(q)))
             .order_by(Document.id.desc())
             .limit(50)
        )

    scored: List[Dict[str, Any]] = []
    for d in docs:
        scored.append({
            "id": f"doc_{d.id}",
            "title": d.title,
            "score": simple_score(query, d.text + " " + d.title),
            "preview": (d.text[:160] + "…") if len(d.text) > 160 else d.text
        })

    # If nothing matched, fetch a few recent docs and still answer
    if not scored:
        with SessionLocal() as s:
            recent = list(s.query(Document).order_by(Document.id.desc()).limit(5))
        for d in recent:
            scored.append({
                "id": f"doc_{d.id}",
                "title": d.title,
                "score": simple_score(query, d.text + " " + d.title),
                "preview": (d.text[:160] + "…") if len(d.text) > 160 else d.text
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    contexts = scored[:topk]

    # Demo “answer” – take the best preview or a generic string
    answer = contexts[0]["preview"] if contexts else "No matching documents yet."

    return jsonify({"ok": True, "answer": answer, "contexts": contexts})

# ---------- WSGI entry ----------
# This is what waitress / gunicorn imports: app:app
if __name__ == "__main__":
    # Local dev runner
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)





























































