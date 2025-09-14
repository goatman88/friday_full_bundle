# src/rag_plus.py
import math
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text

bp = Blueprint("rag_plus", __name__)

def _engine():
    return current_app.extensions["sqlalchemy_engine"] if "sqlalchemy_engine" in current_app.extensions else current_app.config.get("engine")

# piggyback: app.py put the Engine into config for easy access
@bp.record
def _inject_app(setup_state):
    app = setup_state.app
    if "engine" not in app.config:
        # app.app_context() in app.py populated it implicitly
        app.config["engine"] = app.view_functions["root"].__globals__["engine"]  # type: ignore
    app.extensions["sqlalchemy_engine"] = app.config["engine"]

def _bearer():
    tok = request.headers.get("Authorization","")
    return tok.split(" ",1)[1].strip() if tok.startswith("Bearer ") else None

@bp.post("/api/rag/ingest")
def rag_ingest():
    """Batch ingest: [{title,text,source,user_id}]"""
    if not _bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"ok":False,"error":"items[] required"}), 400

    embed_text = current_app.view_functions["rag_query"].__globals__["embed_text"]  # reuse
    engine = _engine()

    inserted = []
    with engine.begin() as conn:
        for it in items:
            title = (it.get("title") or "").strip()
            txt = (it.get("text") or "").strip()
            if not txt: continue
            src = (it.get("source") or "").strip()
            uid = (it.get("user_id") or "public").strip()
            mime = (it.get("mime") or "text/plain").strip()
            vec = embed_text(f"{title}\n\n{txt}") if embed_text else None
            row = conn.execute(text("""
                INSERT INTO documents (title, text, mime, source, user_id, embedding, embedding_vec)
                VALUES (:title, :text, :mime, :source, :user_id, :embedding, :embedding_vec)
                RETURNING id, title
            """), {
                "title": title or None, "text": txt, "mime": mime,
                "source": src or None, "user_id": uid or None,
                "embedding": vec if vec else None,
                "embedding_vec": vec if vec else None
            }).mappings().first()
            inserted.append({"id": row["id"], "title": row["title"]})
    return jsonify({"ok":True, "count": len(inserted), "inserted": inserted}), 200

@bp.post("/api/rag/query-advanced")
def rag_query_advanced():
    """Hybrid: vector → keyword rerank → packed context."""
    if not _bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    q = (body.get("query") or "").strip()
    topk = max(1, min(10, int(body.get("topk") or 5)))
    uid = (body.get("user_id") or "public").strip()
    if not q: return jsonify({"ok":False,"error":"Missing 'query'"}), 400

    engine = _engine()
    embed_text = current_app.view_functions["rag_query"].__globals__["embed_text"]
    qvec = embed_text(q) if embed_text else None

    # Step 1: vector candidate pool
    candidates: List[Dict[str,Any]] = []
    if qvec:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT id, title, text, source,
                       1 - (embedding_vec <=> :qvec) AS sim
                FROM documents
                WHERE embedding_vec IS NOT NULL
                  AND COALESCE(user_id,'public') IN (:uid,'public')
                ORDER BY embedding_vec <=> :qvec
                LIMIT :k
            """), {"qvec": qvec, "uid": uid, "k": topk*4}).mappings().all()
        for r in rows:
            candidates.append({
                "id": r["id"], "title": r["title"], "text": r["text"],
                "source": r["source"], "vscore": float(r["sim"])
            })
    else:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT id, title, text, source, created_at
                FROM documents
                WHERE COALESCE(user_id,'public') IN (:uid,'public')
                ORDER BY created_at DESC LIMIT 200
            """), {"uid": uid}).mappings().all()
        candidates = [{"id":r["id"],"title":r["title"],"text":r["text"],"source":r["source"],"vscore":0.0} for r in rows]

    # Step 2: keyword rerank
    ql = q.lower()
    def kw_score(t: str) -> float:
        t = (t or "").lower()
        return t.count(ql)

    for c in candidates:
        c["kws"] = kw_score(c["title"]) * 3 + kw_score(c["text"])

    # Step 3: combine & pick top K
    candidates.sort(key=lambda x: (x["vscore"], x["kws"]), reverse=True)
    picked = candidates[:topk]

    # Step 4: pack context
    contexts = [{
        "id": p["id"], "title": p["title"],
        "preview": (p["text"] or "")[:400],
        "vscore": round(p["vscore"],4), "kws": float(p["kws"]),
        "source": p["source"]
    } for p in picked]

    return jsonify({"ok":True, "used_embeddings": bool(qvec), "contexts":contexts}), 200

