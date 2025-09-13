import os
import time
import uuid
from typing import Dict, Any, List

from flask import Flask, jsonify, request
from flask_cors import CORS

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

API_TOKEN = os.getenv("API_TOKEN", "").strip()

# Simple in-memory "database" for notes indexed via /api/rag/index
DOCS: Dict[str, Dict[str, Any]] = {}

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def require_auth():
    """Return (ok, error_json_response) if auth fails; otherwise (True, None)."""
    # Expect:  Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if not API_TOKEN:
        # If the server has no token configured, treat as locked down
        return False, (jsonify({"ok": False, "error": "Server missing API_TOKEN"}), 500)

    if not auth.lower().startswith("bearer "):
        return False, (jsonify({"ok": False, "error": "Unauthorized"}), 401)

    token = auth.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        return False, (jsonify({"ok": False, "error": "Unauthorized"}), 401)

    return True, None

def list_routes() -> List[Dict[str, Any]]:
    return [
        {"endpoint": "home", "rule": "/", "methods": ["GET"]},
        {"endpoint": "health", "rule": "/health", "methods": ["GET"]},
        {"endpoint": "routes", "rule": "/__routes", "methods": ["GET"]},
        {"endpoint": "rag_index", "rule": "/api/rag/index", "methods": ["POST"]},
        {"endpoint": "rag_query", "rule": "/api/rag/query", "methods": ["POST"]},
    ]

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"ok": True, "message": "Friday backend is running."}), 200

@app.route("/health", methods=["GET"])
def health():
    """Public health probe (no auth)."""
    return (
        jsonify(
            {
                "ok": True,
                "status": "running",
                "time": _now_iso(),
                "key_present": bool(API_TOKEN),
            }
        ),
        200,
    )

@app.route("/__routes", methods=["GET"])
def routes():
    ok, err = require_auth()
    if not ok:
        return err
    return jsonify({"ok": True, "routes": list_routes()}), 200

@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    ok, err = require_auth()
    if not ok:
        return err

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    text = (data.get("text") or "").strip()
    source = (data.get("source") or "note").strip()

    if not text:
        return jsonify({"ok": False, "error": "Field 'text' is required."}), 400

    doc_id = data.get("id") or f"doc_{int(time.time()*1000)}"
    DOCS[doc_id] = {
        "id": doc_id,
        "title": title or "Untitled",
        "text": text,
        "source": source,
        "created": _now_iso(),
    }
    return jsonify({"ok": True, "indexed": doc_id, "title": DOCS[doc_id]["title"], "chars": len(text)}), 200

@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    ok, err = require_auth()
    if not ok:
        return err

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    topk = int(data.get("topk") or 2)
    topk = max(1, min(topk, 10))

    if not query:
        return jsonify({"ok": False, "error": "Field 'query' is required."}), 400

    # Super-simple “contains” scoring
    scored = []
    q_lower = query.lower()
    for d in DOCS.values():
        t = f"{d.get('title','')} | {d.get('text','')}".lower()
        score = (q_lower in t) * 1.0  # 1.0 if contains, else 0.0
        if score > 0:
            scored.append({"id": d["id"], "title": d["title"], "preview": d["text"][:120], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    contexts = scored[:topk]

    # A tiny answer heuristic
    if contexts:
        answer = f"Top {len(contexts)} matches → " + " | ".join(c["preview"] for c in contexts)
    else:
        answer = "No matching notes found."

    return jsonify({"ok": True, "answer": answer, "contexts": contexts}), 200

# ------------------------------------------------------------------------------
# Entrypoint (Render runs with a WSGI server; local dev can use this)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.getenv("DEBUG", "")))























































