from __future__ import annotations
import os, json, math, time
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
from openai import OpenAI
import numpy as np

from . import settings
from .db import db
from .s3_uploads import bp as s3_bp  # you already have this file
# If you mounted s3 endpoints onto a Blueprint named bp earlier, we reuse it.

# ---- Flask app
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.register_blueprint(s3_bp, url_prefix="/api/s3")

# ---- OpenAI client (NO proxies kwarg)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

EMBED_MODEL = "text-embedding-3-small"  # 1536 dims

# ---- Admin guard
def require_admin():
    secret = request.headers.get("X-Admin-Secret") or request.args.get("secret")
    if not settings.ADMIN_SECRET:
        # If not set, allow (useful for local dev)
        return
    if secret != settings.ADMIN_SECRET:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

# ---- Helpers
def embed(text: str) -> List[float]:
    text = text.replace("\n", " ")
    r = client.embeddings.create(model=EMBED_MODEL, input=text)
    return r.data[0].embedding

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

# ---- System routes
@app.route("/health")
def health():
    return jsonify(ok=True, status="running")

@app.route("/__whoami")
def whoami():
    return jsonify({
        "service": settings.SERVICE_NAME,
        "python": os.popen("python --version").read().strip() or "unknown",
        "cwd": os.getcwd(),
        "module_file": __file__,
    })

@app.route("/__routes")
def routes():
    return jsonify(sorted([rule.rule for rule in app.url_map.iter_rules()]))

# ---- Admin UI (static) — protect with secret
@app.route("/admin")
def admin_ui():
    auth = require_admin()
    if auth is not None:
        return auth
    return send_from_directory(app.static_folder, "admin.html")

# ===============================
# ==========   RAG   ============
# ===============================

@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    auth = require_admin()
    if auth is not None: return auth

    data = request.get_json(force=True) or {}
    title   = (data.get("title") or "").strip()
    text    = (data.get("text") or "").strip()
    source  = (data.get("source") or "").strip() or "admin"
    mime    = (data.get("mime") or "").strip() or "text/plain"
    user_id = (data.get("user_id") or "").strip() or "public"

    if not text:
        return jsonify(ok=False, error="text required"), 400

    emb = embed(text)

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (title, text, source, mime, user_id, embedding) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (title, text, source, mime, user_id, emb)
            )
            doc_id = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM documents")
            count = cur.fetchone()[0]

    return jsonify(ok=True, id=doc_id, count=count)

def _vector_search(q_emb: List[float], topk:int=5, user_id:str="public", source:Optional[str]=None):
    where = ["user_id = %s"]
    params: List[Any] = [user_id]
    if source:
        where.append("source = %s")
        params.append(source)
    where_sql = " AND ".join(where) if where else "TRUE"
    sql = f"""
        SELECT id, title, text, source, mime, user_id,
               1 - (embedding <=> %s::vector) AS score
        FROM documents
        WHERE {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    # vector param appears twice (once in select via 1 - distance, once in order)
    params2 = [q_emb] + params + [q_emb, topk]
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params2)
            rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    return rows

def _keyword_search(q: str, topk:int=10, user_id:str="public"):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, text, source, mime, user_id,
                       ts_rank(tsv, plainto_tsquery('english', %s)) AS score
                FROM documents
                WHERE user_id = %s
                ORDER BY tsv @@ plainto_tsquery('english', %s) DESC, score DESC
                LIMIT %s
                """,
                (q, user_id, q, topk)
            )
            rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    return rows

@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    data = request.get_json(force=True) or {}
    q     = (data.get("query") or "").strip()
    topk  = int(data.get("topk") or 3)
    user  = (data.get("user_id") or "public").strip()
    if not q:
        return jsonify(ok=False, error="query required"), 400

    q_emb = embed(q)
    rows = _vector_search(q_emb, topk=topk, user_id=user)
    return jsonify(ok=True, items=rows)

# ---- Advanced: hybrid + rerank (local cosine)
@app.route("/api/rag/query-advanced", methods=["POST"])
def rag_query_advanced():
    data = request.get_json(force=True) or {}
    q     = (data.get("query") or "").strip()
    topk  = int(data.get("topk") or 5)
    user  = (data.get("user_id") or "public").strip()
    source= (data.get("source") or "").strip() or None
    if not q:
        return jsonify(ok=False, error="query required"), 400

    q_emb = embed(q)
    by_vec = _vector_search(q_emb, topk=max(10, topk), user_id=user, source=source)
    by_kw  = _keyword_search(q, topk=max(10, topk), user_id=user)

    # pool & dedupe
    pool = {}
    for r in by_vec + by_kw:
        pool[r["id"]] = r
    items = list(pool.values())

    # rerank by cosine to embedding of each document text (cheap: embed q only)
    # we already have vector score; boost if also matched keyword.
    def score(item):
        vec_score = item.get("score", 0.0)
        kw_bonus  = 0.15 if item["id"] in {x["id"] for x in by_kw} else 0.0
        return vec_score + kw_bonus

    items.sort(key=score, reverse=True)
    return jsonify(ok=True, items=items[:topk])

# ---- Management: list, delete, feedback
@app.route("/api/rag/list", methods=["GET"])
def rag_list():
    auth = require_admin()
    if auth is not None: return auth
    limit = int(request.args.get("limit", "50"))
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, left(text, 300) AS preview, source, mime, user_id, created_at FROM documents ORDER BY id DESC LIMIT %s", (limit,))
            rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    return jsonify(ok=True, items=rows)

@app.route("/api/rag/delete/<int:doc_id>", methods=["DELETE"])
def rag_delete(doc_id: int):
    auth = require_admin()
    if auth is not None: return auth
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
    return jsonify(ok=True, deleted=doc_id)

@app.route("/api/rag/feedback", methods=["POST"])
def rag_feedback():
    # simple hook to log feedback server-side (extend to a table if you want)
    auth = require_admin()
    if auth is not None: return auth
    data = request.get_json(force=True) or {}
    print("[FEEDBACK]", json.dumps(data))
    return jsonify(ok=True)
















































































