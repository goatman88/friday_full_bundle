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
# --- app.py (or your entry file) ---

from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Health: define ONCE only ---
@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running"
    }), 200

# --- Admin route to list routes (protected by token) ---
import os
API_TOKEN = os.getenv("API_TOKEN", "")

def _authed(req) -> bool:
    auth = req.headers.get("Authorization", "")
    return API_TOKEN and auth == f"Bearer {API_TOKEN}"

@app.get("/__routes")
def list_routes():
    if not _authed(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    out = []
    for rule in app.url_map.iter_rules():
        out.append({
            "rule": str(rule),
            "endpoint": rule.endpoint,
            "methods": sorted(list(rule.methods - {"HEAD", "OPTIONS"}))
        })
    return jsonify({"ok": True, "routes": out}), 200

# --- RAG endpoints (stubs – keep if you already have working versions) ---
@app.post("/api/rag/index")
def rag_index():
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "indexed": True, "echo": data}), 200

@app.post("/api/rag/query")
def rag_query():
    data = request.get_json(silent=True) or {}
    q = data.get("query") or ""
    return jsonify({
        "ok": True,
        "answer": f"Echo: {q}",
        "contexts": [{"title":"demo","preview":"example","score":1.0}]
    }), 200

# --- Render/Gunicorn entry point ---
if __name__ == "__main__":
    # Local dev only
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)



















































