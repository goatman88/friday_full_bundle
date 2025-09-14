import os
import sys
import json
import time
import math
import platform
from dataclasses import dataclass
from typing import List, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
# at top of src/app.py
from openai_client import make_openai_client

# somewhere in your startup/init code:
oai = make_openai_client()

# --- DB driver shims (supports psycopg3 or psycopg2) -------------------------
try:
    import psycopg  # v3
    HAVE_PSYCOPG3 = True
except ImportError:  # fallback to v2
    import psycopg2 as psycopg  # alias for code below
    HAVE_PSYCOPG3 = False

from sqlalchemy import (
    create_engine, text, Column, Integer, String, DateTime, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from pgvector.sqlalchemy import Vector

# --- OpenAI client (no proxies kwarg in 1.x) ---------------------------------
from openai import OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY")
oai = OpenAI(api_key=OPENAI_API_KEY)

# --- Configuration ------------------------------------------------------------
API_TOKEN = os.environ.get("API_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    # Normalize heroku/render style to SQLAlchemy form
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# choose driver piece
driver = "psycopg" if HAVE_PSYCOPG3 else "psycopg2"
if DATABASE_URL.startswith("postgresql://") and f"+{driver}://" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", f"postgresql+{driver}://", 1)

# pool_pre_ping to avoid stale conns on Render
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None

# --- SQLAlchemy Models --------------------------------------------------------
class Base(DeclarativeBase):
    pass

class Doc(Base):
    __tablename__ = "docs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), default="public")
    title: Mapped[str] = mapped_column(String(400))
    source: Mapped[Optional[str]] = mapped_column(String(120))
    mime: Mapped[Optional[str]] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(String)
    # 1536 for text-embedding-3-small; bump to 3072 if you change model
    embedding: Mapped[List[float]] = mapped_column(Vector(1536))
    created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

# --- Bootstrap / migrations on startup ---------------------------------------
def bootstrap_db():
    if not engine:
        return
    with engine.begin() as conn:
        # Enable extension (safe if already exists)
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        # Create table if needed
        Base.metadata.create_all(bind=conn)

        # Make sure we have useful indexes (IVFFLAT + HNSW optional)
        # For cosine distance, we need vector_cosine_ops
        conn.exec_driver_sql("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'docs_embedding_ivfflat'
          ) THEN
            CREATE INDEX docs_embedding_ivfflat
            ON docs USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
          END IF;
        END $$;
        """)

# --- Embeddings ---------------------------------------------------------------
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIMS = 1536  # match the model above

def embed_text(texts: List[str]) -> List[List[float]]:
    # OpenAI 1.x embeddings API
    resp = oai.embeddings.create(model=EMBED_MODEL, input=texts)
    # return in the same order
    return [d.embedding for d in resp.data]

# --- Auth helper --------------------------------------------------------------
def require_auth():
    if not API_TOKEN:
        return  # open if token missing
    hdr = request.headers.get("Authorization", "")
    if not hdr.startswith("Bearer "):
        return ("Missing/invalid token", 401)
    if hdr.split(" ", 1)[1].strip() != API_TOKEN.strip():
        return ("Unauthorized", 401)

# --- Flask app ---------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/")
def root():
    return jsonify({
        "message": "Friday backend is running",
        "ok": True,
        "routes": ["/", "/__routes", "/__whoami", "/api/rag/index", "/api/rag/query", "/health", "/ping", "/static/<path:filename>"],
    })

@app.route("/__routes")
def routes():
    output = [str(r.rule) for r in app.url_map.iter_rules()]
    return jsonify(output)

@app.route("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(time.time_ns() % 10**12),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": platform.python_version(),
    })

@app.route("/health")
def health():
    try:
        if engine:
            with engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
        return jsonify({"ok": True, "status": "running"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/ping")
def ping():
    return "pong", 200

# --- RAG: index ---------------------------------------------------------------
@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    auth = require_auth()
    if auth:
        return auth

    payload = request.get_json(force=True, silent=True) or {}
    title = (payload.get("title") or "").strip() or "Untitled"
    text_body = (payload.get("text") or "").strip()
    source = (payload.get("source") or "").strip() or "unknown"
    mime = (payload.get("mime") or "text/plain").strip()
    user_id = (payload.get("user_id") or "public").strip()

    if not text_body:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400

    # Compute embedding
    vec = embed_text([text_body])[0]
    if len(vec) != EMBED_DIMS:
        return jsonify({"ok": False, "error": f"Embedding dims {len(vec)} != {EMBED_DIMS}"}), 500

    with Session(engine) as s:
        doc = Doc(user_id=user_id, title=title, source=source, mime=mime, text=text_body, embedding=vec)
        s.add(doc)
        s.commit()
        return jsonify({"ok": True, "indexed": {"id": doc.id, "title": doc.title}})

# --- RAG: query ---------------------------------------------------------------
@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    auth = require_auth()
    if auth:
        return auth

    payload = request.get_json(force=True, silent=True) or {}
    query = (payload.get("query") or "").strip()
    topk = int(payload.get("topk") or 3)
    user_id = (payload.get("user_id") or "public").strip()

    if not query:
        return jsonify({"ok": False, "error": "Missing 'query'"}), 400
    topk = max(1, min(topk, 20))

    qvec = embed_text([query])[0]

    # Cosine distance operator <=> when index opclass is vector_cosine_ops
    sql = text("""
        SELECT id, title, source, mime, left(text, 280) AS preview,
               1 - (embedding <=> :qv) AS score
        FROM docs
        WHERE user_id = :uid
        ORDER BY embedding <=> :qv
        LIMIT :k;
    """)
    with engine.connect() as c:
        # psycopg expects vector as list of floats; SQLAlchemy will adapt
        rows = c.execute(sql, {"qv": qvec, "k": topk, "uid": user_id}).mappings().all()

    return jsonify({
        "ok": True,
        "answer": "",  # you can add LLM synthesis here
        "contexts": [dict(r) for r in rows]
    })

# --- Static files passthrough (optional) --------------------------------------
@app.route("/static/<path:filename>")
def static_proxy(filename):
    return send_from_directory(app.static_folder, filename)

# --- App startup --------------------------------------------------------------
def _startup():
    if not DATABASE_URL:
        print("[WARN] DATABASE_URL is not set; vector features will fail.", file=sys.stderr)
    else:
        bootstrap_db()
    if not OPENAI_API_KEY:
        print("[WARN] OPENAI_API_KEY is not set; embeddings will fail.", file=sys.stderr)

_startup()  # run at import time for waitress

# expose `app` for waitress-serve app:app


































































