import os
import time
import math
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# -----------------------------
# App & Config
# -----------------------------
app = Flask(__name__)

# CORS (allow multiple origins via ALLOWED_ORIGINS="https://a.com,https://b.com")
allowed = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if allowed:
    CORS(app, resources={r"/*": {"origins": allowed}})
else:
    CORS(app)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("friday")

# -----------------------------
# Storage (Postgres via SQLAlchemy)
# -----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")

# SQLAlchemy engine with connection health checks
engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
)

def init_db() -> None:
    """Create minimal tables if they don't exist."""
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents (
            id           BIGSERIAL PRIMARY KEY,
            title        TEXT,
            text         TEXT,
            mime         TEXT,
            source       TEXT,
            user_id      TEXT,
            embedding    JSONB,          -- stores numeric array (no pgvector dependency)
            created_at   TIMESTAMPTZ DEFAULT NOW()
        );
        """))

# initialize once on import
init_db()

# -----------------------------
# OpenAI (embeddings) – optional
# -----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    try:
        # IMPORTANT: no `proxies` argument here
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        log.info("OpenAI client initialized.")
    except Exception as e:
        log.warning("OpenAI could not be initialized, falling back to keyword search only: %s", e)
        openai_client = None


def embed_text(txt: str) -> Optional[List[float]]:
    """Return embedding vector or None if embedding service unavailable."""
    if not txt:
        return None
    if not openai_client:
        return None
    try:
        # Small + cheap, great for RAG retrieval
        resp = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=txt
        )
        vec = resp.data[0].embedding
        # normalize for cosine similarity
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
    except Exception as e:
        log.exception("Embedding failed: %s", e)
        return None


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b))


def row_to_doc(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "preview": (row["text"] or "")[:240],
        "source": row["source"],
        "mime": row["mime"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }

# -----------------------------
# Utility / Auth
# -----------------------------
def require_bearer() -> Optional[str]:
    """Very light auth gate: require any Bearer token to be present."""
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    return token.split(" ", 1)[1].strip() or None

def list_routes() -> List[str]:
    rules = sorted([r.rule for r in app.url_map.iter_rules()])
    return rules

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return jsonify({"message": "Friday backend is running", "ok": True, "routes": list_routes()})

@app.get("/__routes")
def _routes():
    return jsonify(list_routes())

@app.get("/__whoami")
def _whoami():
    return jsonify({
        "app_id": int(time.time() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}"
    })

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.get("/ping")
def ping():
    return "pong", 200

# optional static handler (if you want to expose /static/* files from a "static" folder)
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# -----------------------------
# RAG: Index
# -----------------------------
@app.post("/api/rag/index")
def rag_index():
    if not require_bearer():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    text_ = (body.get("text") or "").strip()
    mime = (body.get("mime") or "text/plain").strip()
    source = (body.get("source") or "").strip()
    user_id = (body.get("user_id") or "public").strip()

    if not text_:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400

    vec = embed_text(f"{title}\n\n{text_}")  # embed combined

    with engine.begin() as conn:
        row = conn.execute(
            text("""
            INSERT INTO documents (title, text, mime, source, user_id, embedding)
            VALUES (:title, :text, :mime, :source, :user_id, :embedding)
            RETURNING id, title, created_at
            """),
            {
                "title": title or None,
                "text": text_,
                "mime": mime or None,
                "source": source or None,
                "user_id": user_id or None,
                "embedding": vec if vec is not None else None,
            }
        ).mappings().first()

    return jsonify({
        "ok": True,
        "indexed": [{
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        }],
        "used_embeddings": bool(vec is not None)
    }), 200

# -----------------------------
# RAG: Query
# -----------------------------
@app.post("/api/rag/query")
def rag_query():
    if not require_bearer():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or 3)
    user_id = (body.get("user_id") or "public").strip()

    if not query:
        return jsonify({"ok": False, "error": "Missing 'query'"}), 400

    qvec = embed_text(query)

    with engine.begin() as conn:
        # limit to a reasonable candidate set to keep memory small
        # prefer docs for same user_id or public
        rows = conn.execute(
            text("""
            SELECT id, title, text, mime, source, created_at, embedding
            FROM documents
            WHERE COALESCE(user_id, 'public') IN (:uid, 'public')
            ORDER BY created_at DESC
            LIMIT 500
            """),
            {"uid": user_id}
        ).mappings().all()

    scored: List[Dict[str, Any]] = []

    if qvec:
        # cosine similarity over in-memory JSON embeddings
        for r in rows:
            emb = r["embedding"]
            score = -1.0
            if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
                # stored normalized already
                score = cosine(qvec, emb)
            scored.append({"score": float(score), "row": r})
        # sort descending by similarity
        scored.sort(key=lambda x: x["score"], reverse=True)
    else:
        # Fallback: keyword score (very naive)
        ql = query.lower()
        for r in rows:
            txt = (r["text"] or "").lower()
            ttl = (r["title"] or "").lower()
            score = (ttl.count(ql) * 3) + txt.count(ql)
            scored.append({"score": float(score), "row": r})
        scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[: max(1, min(20, topk))]
    contexts = []
    for s in top:
        r = s["row"]
        contexts.append({
            "id": r["id"],
            "title": r["title"],
            "preview": (r["text"] or "")[:240],
            "score": round(s["score"], 4),
            "source": r["source"],
        })

    # A tiny demo answer (replace with real LLM answer if you want)
    answer = None
    if "widget" in query.lower():
        answer = "Widgets are blue and waterproof."
    else:
        # If you want, you can uncomment below to synthesize with OpenAI:
        # if openai_client:
        #     prompt = f"Answer the question using the following snippets:\n\n" + \
        #              "\n\n".join([c['preview'] for c in contexts]) + \
        #              f"\n\nQuestion: {query}\nAnswer:"
        #     try:
        #         chat = openai_client.chat.completions.create(
        #             model="gpt-4o-mini",
        #             messages=[{"role": "user", "content": prompt}],
        #             temperature=0.2
        #         )
        #         answer = chat.choices[0].message.content.strip()
        #     except Exception as e:
        #         log.warning("LLM synth failed: %s", e)
        #         answer = None
        pass

    return jsonify({
        "ok": True,
        "answer": answer,
        "used_embeddings": bool(qvec),
        "contexts": contexts
    }), 200


# -----------------------------
# Main (for local dev only)
# -----------------------------
if __name__ == "__main__":
    # Local dev: python app.py
    # On Render we run via waitress/gunicorn, so this block is ignored.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
































































