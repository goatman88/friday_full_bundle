# src/app.py
import os, time, math, logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
# db_compat.py (inline shim)
try:
    import psycopg  # v3
    HAVE_PSYCOPG3 = True
except ImportError:             # fallback to v2
    import psycopg2 as psycopg  # alias so rest of code can use `psycopg`
    HAVE_PSYCOPG3 = False

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("friday")

# ---- Flask + CORS -----------------------------------------------------------
app = Flask(__name__)
allowed = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
CORS(app, resources={r"/*": {"origins": allowed}}) if allowed else CORS(app)

# ---- DB ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents (
          id            BIGSERIAL PRIMARY KEY,
          title         TEXT,
          text          TEXT,
          mime          TEXT,
          source        TEXT,
          user_id       TEXT,
          embedding     JSONB,
          embedding_vec VECTOR(1536),
          created_at    TIMESTAMPTZ DEFAULT NOW()
        )"""))
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_documents_embedding_vec_cosine
        ON documents
        USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)
        """))
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_documents_user_id
        ON documents (COALESCE(user_id,'public'))
        """))
init_db()

# ---- OpenAI (optional) ------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)  # no proxies kwarg
        log.info("OpenAI client initialized.")
    except Exception as e:
        log.warning("OpenAI init failed: %s", e)

def embed_text(txt: str) -> Optional[List[float]]:
    """Return L2-normalized embedding or None if disabled/unavailable."""
    if not txt or not openai_client:
        return None
    try:
        r = openai_client.embeddings.create(model="text-embedding-3-small", input=txt)
        vec = r.data[0].embedding
        norm = math.sqrt(sum(v*v for v in vec)) or 1.0
        return [v / norm for v in vec]
    except Exception as e:
        log.exception("Embedding failed: %s", e)
        return None

def list_routes():
    return sorted([r.rule for r in app.url_map.iter_rules()])

def require_bearer() -> Optional[str]:
    tok = request.headers.get("Authorization", "")
    if not tok.startswith("Bearer "): return None
    return tok.split(" ",1)[1].strip() or None

# ---- Core health/info -------------------------------------------------------
@app.get("/")
def root():
    return jsonify({"message":"Friday backend is running","ok":True,"routes":list_routes()})

@app.get("/__routes")
def _routes(): return jsonify(list_routes())

@app.get("/__whoami")
def _whoami():
    return jsonify({
        "app_id": int(time.time()*1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}",
    })

@app.get("/health")
def health(): return jsonify({"ok":True,"status":"running"}), 200

@app.get("/ping")
def ping(): return "pong", 200

@app.get("/static/<path:filename>")
def static_files(filename): return send_from_directory("static", filename)

# ---- Basic RAG endpoints (kept here for simplicity) ------------------------
@app.post("/api/rag/index")
def rag_index():
    if not require_bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    text_ = (body.get("text") or "").strip()
    mime = (body.get("mime") or "text/plain").strip()
    source = (body.get("source") or "").strip()
    user_id = (body.get("user_id") or "public").strip()
    if not text_:
        return jsonify({"ok":False,"error":"Missing 'text'"}), 400

    vec = embed_text(f"{title}\n\n{text_}")

    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO documents (title, text, mime, source, user_id, embedding, embedding_vec)
            VALUES (:title, :text, :mime, :source, :user_id, :embedding, :embedding_vec)
            RETURNING id, title, created_at
        """), {
            "title": title or None,
            "text": text_,
            "mime": mime or None,
            "source": source or None,
            "user_id": user_id or None,
            "embedding": vec if vec else None,
            "embedding_vec": vec if vec else None,
        }).mappings().first()

    return jsonify({
        "ok": True,
        "indexed": [{"id": row["id"], "title": row["title"], "created_at": row["created_at"].isoformat() if row["created_at"] else None}],
        "used_embeddings": bool(vec)
    }), 200

@app.post("/api/rag/query")
def rag_query():
    if not require_bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = max(1, min(20, int(body.get("topk") or 3)))
    user_id = (body.get("user_id") or "public").strip()
    if not query:
        return jsonify({"ok":False,"error":"Missing 'query'"}), 400

    qvec = embed_text(query)
    contexts: List[Dict[str, Any]] = []

    if qvec:
        # Vector ANN (cosine distance) — requires embedding_vec IS NOT NULL
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT id, title, text, source, mime, created_at,
                       1 - (embedding_vec <=> :qvec) AS sim
                FROM documents
                WHERE embedding_vec IS NOT NULL
                  AND COALESCE(user_id,'public') IN (:uid, 'public')
                ORDER BY embedding_vec <=> :qvec
                LIMIT :k
            """), {"qvec": qvec, "uid": user_id, "k": topk}).mappings().all()

        for r in rows:
            contexts.append({
                "id": r["id"],
                "title": r["title"],
                "preview": (r["text"] or "")[:240],
                "score": round(float(r["sim"]), 4),
                "source": r["source"],
            })
    else:
        # Keyword fallback (recent 500; naive ranking)
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT id, title, text, source, mime, created_at
                FROM documents
                WHERE COALESCE(user_id,'public') IN (:uid, 'public')
                ORDER BY created_at DESC
                LIMIT 500
            """), {"uid": user_id}).mappings().all()
        ql = query.lower()
        scored = []
        for r in rows:
            ttl = (r["title"] or "").lower()
            txt = (r["text"] or "").lower()
            s = (ttl.count(ql) * 3) + txt.count(ql)
            scored.append((s, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        for s, r in scored[:topk]:
            contexts.append({
                "id": r["id"], "title": r["title"],
                "preview": (r["text"] or "")[:240],
                "score": float(s), "source": r["source"]
            })

    answer = "Widgets are blue and waterproof." if "widget" in query.lower() else None
    return jsonify({"ok":True, "answer":answer, "used_embeddings": bool(qvec), "contexts":contexts}), 200

# ---- Register advanced modules (blueprints) --------------------------------
try:
    from rag_plus import bp as rag_bp
    app.register_blueprint(rag_bp)
except Exception as e:
    log.warning("rag_plus not loaded: %s", e)

try:
    from voice import bp as voice_bp
    app.register_blueprint(voice_bp)
except Exception as e:
    log.warning("voice not loaded: %s", e)

try:
    from vision import bp as vision_bp
    app.register_blueprint(vision_bp)
except Exception as e:
    log.warning("vision not loaded: %s", e)

try:
    from jobs import start_scheduler
    start_scheduler(engine, embed_text)
except Exception as e:
    log.warning("jobs scheduler not started: %s", e)

# ---- Local dev --------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

































































