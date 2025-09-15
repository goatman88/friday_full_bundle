import os
import sys
import platform
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# ---- Logging (fix: use constant, not string) ----
logging.basicConfig(
    level=logging.INFO,               # <— IMPORTANT: constant, not "info"
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("app")

# ---- Flask app ----
app = Flask(__name__)

# ---- CORS ----
# If FRONTEND_ORIGIN is set, allow only that; otherwise allow all (for now).
frontend_origin = os.getenv("FRONTEND_ORIGIN")
cors_resources = {r"/*": {"origins": frontend_origin or "*"}}
CORS(app, resources=cors_resources, supports_credentials=True)

# ---- Health & diagnostics ----
@app.get("/health")
def health():
    return jsonify(ok=True, status="running", ts=datetime.utcnow().isoformat() + "Z")

@app.get("/ping")
def ping():
    return jsonify(pong=True)

@app.get("/__routes")
def list_routes():
    routes = sorted({rule.rule for rule in app.url_map.iter_rules()})
    return jsonify(routes)

@app.get("/__whoami")
def whoami():
    try:
        module_file = __file__
    except Exception:
        module_file = "unknown"
    return jsonify({
        "cwd": os.getcwd(),
        "module_file": module_file,
        "python": f"Python {platform.python_version()}",
        "app_env": {
            "FRONTEND_ORIGIN": frontend_origin or "*",
        }
    })

# ---- Friendly echo (handy for quick tests) ----
@app.post("/echo")
def echo():
    payload = request.get_json(silent=True) or {}
    return jsonify(received=payload, headers=dict(request.headers))

# ---- Minimal RAG placeholders so existing smoke scripts keep working ----
# You can replace these with your real vector/DB-backed handlers later.
_INMEM_DOCS = []  # [{title, text, source, mime, user_id}]
@app.post("/api/rag/index")
def rag_index():
    doc = request.get_json(force=True)
    # keep a tiny subset, don’t crash if fields are missing
    _INMEM_DOCS.append({
        "title": doc.get("title"),
        "text": doc.get("text"),
        "source": doc.get("source"),
        "mime": doc.get("mime", "text/plain"),
        "user_id": doc.get("user_id", "public"),
        "ts": datetime.utcnow().isoformat() + "Z",
    })
    return jsonify(ok=True, count=len(_INMEM_DOCS))

@app.post("/api/rag/query")
def rag_query():
    body = request.get_json(force=True)
    q = (body or {}).get("query", "")
    topk = int((body or {}).get("topk", 3))
    # naive keyword filter so smoke tests return something predictable
    hits = []
    for d in _INMEM_DOCS:
        score = (d["text"] or "").lower().count(q.lower()) if q else 0
        if score > 0 or q == "":
            hits.append({
                "title": d["title"],
                "chunk": d["text"],
                "source": d["source"],
                "score": float(score),
            })
    hits.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(query=q, results=hits[:topk])

# Root
@app.get("/")
def root():
    return jsonify(ok=True, service="friday", message="It works. See /health, /__routes, /__whoami."))


# ---- Optional: OpenAI client (SAFE init, no proxies kw) ----
# Leave this here for later; it won’t run unless you use it explicitly.
# from openai import OpenAI
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# if OPENAI_API_KEY:
#     oai = OpenAI(api_key=OPENAI_API_KEY)  # <— no proxies kw anywhere


if __name__ == "__main__":
    # Local dev
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))














































































