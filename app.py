# src/app.py
from __future__ import annotations

import os
import re
import socket
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from sqlalchemy import (
    create_engine,
    text as sql_text,
    String,
    DateTime,
    Integer,
    Text,
    Float,
    ForeignKey,
    select,
    func,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, Session, relationship
from sqlalchemy.exc import OperationalError, ProgrammingError

# pgvector
from pgvector.sqlalchemy import Vector

# background jobs
from apscheduler.schedulers.background import BackgroundScheduler

# embeddings & LLM
import tiktoken
from openai import OpenAI


# =============================================================================
# Config
# =============================================================================

def normalize_db_url(raw: str | None) -> str:
    if not raw or not raw.strip():
        db_path = os.path.join(os.path.dirname(__file__), "local.db")
        return f"sqlite:///{db_path}"  # SQLite fallback (no vectors)
    url = raw.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

API_TOKEN = os.getenv("API_TOKEN", "").strip()
DB_URL = normalize_db_url(os.getenv("DATABASE_URL"))
SERVICE_NAME = os.getenv("RENDER_SERVICE_NAME", "friday")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")  # 3072 dims
EMBED_DIM = int(os.getenv("EMBED_DIM", "3072"))                    # align with model
LLM_MODEL   = os.getenv("LLM_MODEL", "gpt-4o-mini")

CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

STARTED_AT = time.time()
client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# =============================================================================
# DB setup
# =============================================================================

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(64), default="upload")
    mime: Mapped[str] = mapped_column(String(64), default="text/plain")
    user_id: Mapped[str] = mapped_column(String(64), default="public")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    chunks: Mapped[List["Chunk"]] = relationship(back_populates="doc", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    # semantic vectors (NULL until embedded)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    embedded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    embed_attempts: Mapped[int] = mapped_column(Integer, default=0)

    doc: Mapped[Document] = relationship(back_populates="chunks")

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    future=True,
)

def init_db() -> None:
    # enable pgvector on Postgres; harmless on SQLite (will throw -> caught)
    try:
        if DB_URL.startswith("postgresql+psycopg2://"):
            with engine.begin() as conn:
                conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as e:
        # extension creation not supported (permissions on shared DBs)
        pass
    Base.metadata.create_all(engine)

# build tables at import
try:
    init_db()
except Exception as e:
    # boot anyway; health will show degraded storage
    pass


# =============================================================================
# Flask
# =============================================================================

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})


# =============================================================================
# Helpers
# =============================================================================

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
    if not API_TOKEN:
        return "Server missing API_TOKEN (set env var)"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "Missing Authorization: Bearer <token>"
    if auth.split(" ", 1)[1].strip() != API_TOKEN:
        return "Invalid token"
    return None

def keyword_score(query: str, text: str) -> float:
    q_terms = {t for t in re.findall(r"[A-Za-z0-9]+", query.lower()) if len(t) > 2}
    if not q_terms:
        return 0.0
    t_terms = {t for t in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(t) > 2}
    if not t_terms:
        return 0.0
    inter = q_terms.intersection(t_terms)
    return round(len(inter) / max(1, len(q_terms)), 4)

def chunk_text(text: str, target_tokens=CHUNK_TOKENS, overlap=CHUNK_OVERLAP) -> List[str]:
    """
    Token-aware chunking using tiktoken. Keeps context with small overlap.
    """
    enc = tiktoken.get_encoding("cl100k_base")
    ids = enc.encode(text)
    chunks = []
    i = 0
    while i < len(ids):
        part = ids[i : i + target_tokens]
        chunks.append(enc.decode(part))
        i += max(1, target_tokens - overlap)
    return chunks or [""]


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not client:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    # Batch embed for efficiency
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [e.embedding for e in resp.data]


# =============================================================================
# Background embedding scheduler
# =============================================================================

scheduler = BackgroundScheduler(daemon=True)

def embed_pending_chunks(batch_size: int = 32, max_attempts: int = 5):
    """
    Finds chunks with NULL embedding and embeds them in batches.
    Retries failed items up to max_attempts.
    """
    if not client:
        return
    try:
        with Session(engine) as s:
            # newest first so searches "warm up" quickly
            pending: List[Chunk] = (
                s.query(Chunk)
                 .filter(Chunk.embedding.is_(None))
                 .filter(Chunk.embed_attempts < max_attempts)
                 .order_by(Chunk.id.desc())
                 .limit(batch_size)
                 .all()
            )
            if not pending:
                return

            texts = [c.text for c in pending]
            try:
                vectors = embed_texts(texts)
            except Exception:
                # mark attempts and bail
                for c in pending:
                    c.embed_attempts += 1
                s.commit()
                return

            now = datetime.utcnow()
            for c, v in zip(pending, vectors):
                c.embedding = v
                c.embedded_at = now
                c.embed_attempts += 1
            s.commit()
    except Exception:
        # swallow errors; next tick will retry
        pass

# run every 15s (gentle; Render free tier friendly)
scheduler.add_job(embed_pending_chunks, "interval", seconds=15, jitter=5)
try:
    scheduler.start()
except Exception:
    pass


# =============================================================================
# Routes
# =============================================================================

@app.get("/")
def root():
    return ok({
        "message": "Friday backend is running",
        "status": "running",
        "routes": [r.rule for r in app.url_map.iter_rules()],
    })

@app.get("/__routes")
def list_routes():
    return jsonify(sorted({r.rule for r in app.url_map.iter_rules()}))

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
    try:
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        storage = "ok"
        # check pgvector availability
        vector_ok = False
        if DB_URL.startswith("postgresql+psycopg2://"):
            try:
                with engine.connect() as conn:
                    conn.execute(sql_text("SELECT extname FROM pg_extension WHERE extname='vector'"))
                vector_ok = True
            except Exception:
                pass
    except Exception as e:
        return ok({"status": "running", "storage": f"degraded: {type(e).__name__}"})
    return ok({"status": "running", "storage": storage, "pgvector": vector_ok})

@app.get("/ping")
def ping():
    return ok({"pong": True, "uptime_s": round(time.time() - STARTED_AT, 1)})

@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


# =====================  RAG API  =====================

@app.post("/api/rag/index")
def rag_index():
    unauthorized = require_bearer()
    if unauthorized:
        return err(unauthorized, status=401)

    body = request.get_json(silent=True) or {}
    title  = (body.get("title") or "").strip()[:255]
    text   = (body.get("text") or "").strip()
    source = (body.get("source") or "upload").strip()[:64]
    mime   = (body.get("mime")   or "text/plain").strip()[:64]
    user   = (body.get("user_id") or "public").strip()[:64]

    if not text:
        return err("Field 'text' is required")

    # persist doc + chunks; embeddings will be created in background
    with Session(engine) as s:
        doc = Document(title=title, source=source, mime=mime, user_id=user, text=text)
        s.add(doc)
        s.flush()

        for idx, chunk in enumerate(chunk_text(text)):
            s.add(Chunk(doc_id=doc.id, chunk_index=idx, text=chunk))
        s.commit()

    # trigger a quick pass immediately (best-effort)
    try:
        embed_pending_chunks(batch_size=64)
    except Exception:
        pass

    return ok({"indexed": [{"id": doc.id, "title": doc.title, "chunks": len(chunk_text(text))}]})

def _vector_search(session: Session, user: str, query_vec: List[float], topk: int) -> List[Dict[str, Any]]:
    """
    pgvector cosine similarity using <-> operator (when using cosine distance).
    """
    # raw SQL for performance + explicit cast to vector
    q = session.execute(
        sql_text("""
            SELECT c.id, c.doc_id, c.chunk_index, c.text,
                   1 - (c.embedding <=> :qvec) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE c.embedding IS NOT NULL AND d.user_id = :user
            ORDER BY c.embedding <=> :qvec
            LIMIT :k
        """),
        {"qvec": query_vec, "k": topk, "user": user},
    )
    rows = q.fetchall()
    contexts = []
    for r in rows:
        preview = r.text[:180] + ("…" if len(r.text) > 180 else "")
        contexts.append({
            "id": int(r.id),
            "title": f"Doc {int(r.doc_id)} · chunk {int(r.chunk_index)}",
            "score": float(r.score),
            "preview": preview,
        })
    return contexts

@app.post("/api/rag/query")
def rag_query():
    unauthorized = require_bearer()
    if unauthorized:
        return err(unauthorized, status=401)

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk  = max(1, min(10, int(body.get("topk") or 3)))
    user  = (body.get("user_id") or "public").strip()[:64]

    if not query:
        return err("Field 'query' is required")

    # Try semantic search if we have pgvector + embeddings + OpenAI
    contexts: List[Dict[str, Any]] = []
    used_semantic = False
    try:
        if DB_URL.startswith("postgresql+psycopg2://") and client:
            qvec = embed_texts([query])[0]
            with Session(engine) as s:
                contexts = _vector_search(s, user, qvec, topk)
                used_semantic = len(contexts) > 0
    except Exception:
        contexts = []

    # Fallback: keyword search over most recent docs
    if not contexts:
        with Session(engine) as s:
            docs: List[Document] = (
                s.query(Document)
                 .filter(Document.user_id == user)
                 .order_by(Document.id.desc())
                 .limit(200)
                 .all()
            )
        scored = []
        for d in docs:
            score = keyword_score(query, d.text or "")
            if score > 0:
                scored.append({
                    "id": d.id,
                    "title": d.title or f"Doc {d.id}",
                    "score": score,
                    "preview": (d.text[:180] + "…") if d.text and len(d.text) > 180 else (d.text or "")
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        contexts = scored[:topk]

    # Answer synthesis via LLM (short, cite sources implicitly)
    answer = ""
    if client and contexts:
        try:
            context_text = "\n\n".join([f"[{i+1}] {c['preview']}" for i, c in enumerate(contexts)])
            prompt = (
                "You are a concise assistant. Use the context to answer the user.\n"
                "If unsure, say so. Keep it under 120 words.\n\n"
                f"Question: {query}\n\nContext:\n{context_text}\n\nAnswer:"
            )
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=180,
            )
            answer = resp.choices[0].message.content.strip()
        except Exception:
            # fallback: best preview
            answer = contexts[0]["preview"] if contexts else "No answer."

    if not answer:
        answer = contexts[0]["preview"] if contexts else "No matching context found yet."

    return ok({"answer": answer, "contexts": contexts, "semantic": used_semantic})


# =============================================================================
# Errors
# =============================================================================

@app.errorhandler(404)
def not_found(_):
    return err("Not Found", 404)

@app.errorhandler(405)
def method_not_allowed(_):
    return err("Method Not Allowed", 405)

@app.errorhandler(Exception)
def on_error(ex: Exception):
    return err("Internal Server Error", 500, type=type(ex).__name__, detail=str(ex)[:240])


# =============================================================================
# Local dev
# =============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=bool(os.getenv("DEBUG")))































































