import os
import json
import logging
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, request

# ---- Logging (use constant, not string to avoid "Unknown level: 'info'") ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger("friday")

# ---- Flask app --------------------------------------------------------------
app = Flask(__name__)

# Simple in-memory doc store so the API works even without a DB.
# (Safe for smoke tests; swap with Postgres later.)
_DOCS = []  # each item: {"id": int, "title": ..., "text": ..., "source": ..., "user_id": ...}

# ---- Auth: shared-secret bearer token (simple & Render-friendly) ------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # set in Render > Environment
def require_bearer_token(fn):
    """Require `Authorization: Bearer <ADMIN_TOKEN>` if ADMIN_TOKEN is set."""
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not ADMIN_TOKEN:
            return fn(*args, **kwargs)  # auth disabled
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(ok=False, error="missing_bearer"), 401
        token = header.split(" ", 1)[1]
        if token != ADMIN_TOKEN:
            return jsonify(ok=False, error="invalid_bearer"), 403
        return fn(*args, **kwargs)
    return _wrap

# ---- Utility ---------------------------------------------------------------
def _route_list():
    rules = []
    for r in app.url_map.iter_rules():
        # skip static rule noise
        if r.rule.startswith("/static"):
            continue
        methods = ",".join(sorted(m for m in r.methods if m in {"GET","POST","PUT","DELETE"}))
        rules.append({"path": r.rule, "methods": methods})
    return sorted(rules, key=lambda x: x["path"])

# ---- Core routes ------------------------------------------------------------
@app.get("/")
def root():
    return jsonify(
        ok=True,
        service="friday",
        message="It works. See /health, /__routes, /__whoami."
    )

@app.get("/__routes")
def routes():
    return jsonify([r["path"] for r in _route_list()])

@app.get("/__whoami")
def whoami():
    return jsonify({
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}",
        "app_id": id(app)
    })

@app.get("/health")
def health():
    return jsonify(ok=True, status="running", time=datetime.utcnow().isoformat()+"Z")

# ---- RAG-ish endpoints (in-memory for now; DB layer can be dropped in later)-
@app.post("/api/rag/index")
@require_bearer_token
def rag_index():
    """
    Accepts JSON like:
    {
      "title": "Widget FAQ",
      "text":  "Widgets are blue...",
      "source":"faq",
      "mime":  "text/plain",
      "user_id":"public"
    }
    """
    try:
        data = request.get_json(force=True, silent=False) or {}
        required = ("title","text")
        for k in required:
            if not data.get(k):
                return jsonify(ok=False, error=f"missing_{k}"), 400

        doc_id = len(_DOCS) + 1
        item = {
            "id": doc_id,
            "title": data["title"],
            "text": data["text"],
            "source": data.get("source") or "unknown",
            "mime": data.get("mime") or "text/plain",
            "user_id": data.get("user_id") or "public",
            "created_at": datetime.utcnow().isoformat()+"Z"
        }
        _DOCS.append(item)
        return jsonify(ok=True, id=doc_id, size=len(item["text"])), 201
    except Exception as e:
        log.exception("rag_index failed")
        return jsonify(ok=False, error=str(e)), 500

@app.post("/api/rag/query")
def rag_query():
    """
    Accepts JSON like: { "query": "What color are widgets?", "topk": 3 }
    Returns naive keyword matches from the in-memory docs.
    """
    data = request.get_json(force=True, silent=False) or {}
    q = (data.get("query") or "").strip()
    topk = int(data.get("topk") or 3)
    if not q:
        return jsonify(ok=False, error="missing_query"), 400

    # super simple match score = count of query words appearing in text/title
    words = [w.lower() for w in q.split() if w.strip()]
    scored = []
    for d in _DOCS:
        hay = (d["title"] + " " + d["text"]).lower()
        score = sum(hay.count(w) for w in words)
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda t: t[0], reverse=True)
    hits = [dict(id=d["id"], title=d["title"], source=d["source"], score=score) for score, d in scored[:topk]]

    return jsonify(ok=True, query=q, topk=topk, hits=hits)

# ---- Admin (behind bearer token) -------------------------------------------
@app.get("/admin")
@require_bearer_token
def admin_home():
    return jsonify(
        ok=True,
        routes=[r["path"] for r in _route_list()],
        docs=len(_DOCS)
    )

# ---- Error handlers ---------------------------------------------------------
@app.errorhandler(404)
def _404(_e):
    return jsonify(ok=False, error="not_found"), 404

@app.errorhandler(500)
def _500(e):
    log.exception("Unhandled error")
    return jsonify(ok=False, error="internal_error"), 500

















































































