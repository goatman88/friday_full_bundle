from flask import Flask, jsonify, request, send_from_directory, abort
from openai import OpenAI
import os, math
from typing import Any, Dict, List, Optional

from . import settings
from . import db
from .s3_uploads import s3_bp  # keeps your existing S3 routes

# ---- Flask app & static /admin
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.register_blueprint(s3_bp, url_prefix="/api/s3")

# ---- OpenAI client (no proxies kw)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def require_admin():
    """Protect admin UI & admin endpoints by shared secret."""
    if not settings.ADMIN_SECRET:
        return  # if unset, do not block (you can force it by setting the env)
    key = request.headers.get("X-Admin-Secret") or request.args.get("key")
    if key != settings.ADMIN_SECRET:
        abort(401)

@app.route("/admin")
def admin_ui():
    require_admin()
    return send_from_directory(app.static_folder, "admin.html")

# ---- Diagnostics
@app.route("/health")
def health():
    return jsonify(ok=True, status="running")

@app.route("/__whoami")
def whoami():
    return jsonify({
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip(),
    })

@app.route("/__routes")
def routes():
    rule_list = sorted([str(r) for r in app.url_map.iter_rules()])
    return jsonify(rule_list)

# ---- DB admin (guarded)
@app.route("/admin/init-db", methods=["POST"])
def init_db():
    require_admin()
    return jsonify(db.init_db())

# ---- Embeddings helper
def embed_text(text: str) -> List[float]:
    # OpenAI embeddings v1
    em = client.embeddings.create(model=settings.OPENAI_EMBED_MODEL, input=text)
    return em.data[0].embedding  # List[float]

# ---- RAG: index a doc
@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    body = request.get_json(force=True) or {}
    title = body.get("title") or ""
    text = body.get("text") or ""
    source = body.get("source") or "admin"
    user_id = body.get("user_id") or "public"
    mime = body.get("mime") or "text/plain"
    metadata = body.get("metadata") or {}

    if not text.strip():
        return jsonify(ok=False, error="text is required"), 400

    emb = embed_text(text)
    doc_id = db.insert_doc(title, text, source, user_id, mime, emb, metadata)
    return jsonify(ok=True, id=doc_id)

# ---- RAG: upsert-batch (advanced #1)
@app.route("/api/rag/upsert-batch", methods=["POST"])
def rag_upsert_batch():
    body = request.get_json(force=True) or {}
    items: List[Dict[str, Any]] = body.get("items") or []
    if not items:
        return jsonify(ok=False, error="items[] required"), 400
    rows = []
    for it in items:
        t = (it.get("text") or "").strip()
        if not t:
            continue
        rows.append({
            "title": it.get("title") or "",
            "text": t,
            "source": it.get("source") or "batch",
            "user_id": it.get("user_id") or "public",
            "mime": it.get("mime") or "text/plain",
            "metadata": it.get("metadata") or {},
            "embedding": embed_text(t),
        })
    res = db.upsert_batch(rows)
    return jsonify(res)

# ---- RAG: query (basic cosine)
@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    body = request.get_json(force=True) or {}
    q = body.get("query") or ""
    topk = int(body.get("topk") or 3)
    if not q.strip():
        return jsonify(ok=False, error="query is required"), 400
    qv = embed_text(q)
    rows = db.search_similar(qv, topk=topk)
    return jsonify({"query": q, "topk": topk, "results": rows})

# ---- RAG: query-advanced (advanced #2) - filters + light MMR
@app.route("/api/rag/query-advanced", methods=["POST"])
def rag_query_advanced():
    body = request.get_json(force=True) or {}
    q = body.get("query") or ""
    topk = int(body.get("topk") or 5)
    lambda_mmr = float(body.get("lambda_mmr") or 0.5)  # 0=diverse, 1=similarity
    source = body.get("source")
    user_id = body.get("user_id")
    where_meta = body.get("where_meta")

    if not q.strip():
        return jsonify(ok=False, error="query is required"), 400

    qv = embed_text(q)
    # pull an over-sampled pool
    pool = db.search_similar(qv, topk=max(20, topk*4), source=source, user_id=user_id, where_meta=where_meta)
    # simple MMR
    selected: List[Dict[str,Any]] = []
    selected_vecs: List[List[float]] = []
    def cos(a,b):
        import math
        na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(x*x for x in b))
        return sum(x*y for x,y in zip(a,b)) / (na*nb + 1e-8)
    for cand in pool:
        # NOTE: we do not have vectors of docs here; to keep it light, re-embed top few texts (ok for admin/API usage)
        dv = embed_text(cand["text"][:1500])
        if not selected:
            selected.append(cand); selected_vecs.append(dv); 
        else:
            sim_to_query = cos(dv, qv)
            sim_to_selected = max(cos(dv, sv) for sv in selected_vecs)
            score = lambda_mmr*sim_to_query - (1-lambda_mmr)*sim_to_selected
            cand["_mmr"] = score
            selected.append(cand); selected_vecs.append(dv)
    # sort by mmr if computed
    for c in selected: c["_mmr"] = c.get("_mmr", c.get("score", 0.0))
    selected.sort(key=lambda r: r["_mmr"], reverse=True)
    return jsonify({"query": q, "results": selected[:topk]})

# ---- RAG: delete (advanced #3)
@app.route("/api/rag/delete", methods=["POST"])
def rag_delete():
    require_admin()
    body = request.get_json(force=True) or {}
    idv = body.get("id")
    source = body.get("source")
    res = db.delete_docs(id=idv, source=source)
    return jsonify(res)

# ---- RAG: reindex-embeddings (advanced #4)
@app.route("/api/rag/reindex-embeddings", methods=["POST"])
def rag_reindex():
    require_admin()
    body = request.get_json(force=True) or {}
    limit = int(body.get("limit") or 200)
    # lightweight: recompute for newest N records missing embeddings or to refresh
    with db.get_conn() as conn, conn.cursor(row_factory=db.dict_row) as cur:
        cur.execute("SELECT id, text FROM rag_docs ORDER BY id DESC LIMIT %s;", (limit,))
        rows = cur.fetchall()
        for r in rows:
            v = embed_text(r["text"])
            cur2 = conn.cursor()
            cur2.execute("UPDATE rag_docs SET embedding=%s WHERE id=%s;", (v, r["id"]))
            cur2.close()
    return jsonify(ok=True, updated=min(limit, len(rows)))
















































































