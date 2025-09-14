from __future__ import annotations

import os
from typing import Dict, Any, List
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---- helpers ---------------------------------------------------------------

def _ok(payload: Dict[str, Any] = None, status: int = 200):
    data = {"ok": True}
    if payload:
        data.update(payload)
    return jsonify(data), status

def _err(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status

def _bearer() -> str:
    """Return the raw Bearer token (or empty string)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return ""

# ---- routes ----------------------------------------------------------------

@app.get("/")
def root():
    """Small landing to prove the app that’s deployed is *this* file."""
    return _ok({
        "service": "friday demo",
        "message": "It works. See /health and /_routes.",
        "routes": [r["rule"] for r in _route_table()]
    })

@app.get("/health")
def health():
    return _ok({"status": "running"})

@app.get("/_routes")
def routes():
    """List the live routes so you can compare with local."""
    return _ok({"routes": _route_table()})

def _route_table() -> List[Dict[str, Any]]:
    out = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        out.append({"rule": str(rule), "endpoint": rule.endpoint, "methods": methods})
    return out

@app.post("/api/rag/index")
def rag_index():
    token = _bearer()
    if not token:
        return _err("Unauthorized", 401)

    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    text = str(body.get("text", "")).strip()
    source = str(body.get("source", "")).strip() or "note"

    if not title or not text:
        return _err("Both 'title' and 'text' are required.", 422)

    # Minimal stub: pretend we indexed a single document.
    doc = {"id": "doc_1", "title": title, "source": source, "len": len(text)}
    return _ok({"indexed": [doc]})

@app.post("/api/rag/query")
def rag_query():
    token = _bearer()
    if not token:
        return _err("Unauthorized", 401)

    body = request.get_json(silent=True) or {}
    query = str(body.get("query", "")).strip()
    topk = int(body.get("topk", 2) or 2)

    if not query:
        return _err("'query' is required.", 422)

    contexts = [{
        "id": "doc_1",
        "title": "Widget FAQ",
        "score": 0.42,
        "preview": "Widgets are blue and waterproof."
    }][:max(1, topk)]

    return _ok({
        "answer": "Widgets are blue and waterproof.",
        "contexts": contexts
    })

# ---- error handlers (nicer 404 on Render) ----------------------------------

@app.errorhandler(404)
def not_found(e):
    return _err("Not Found", 404)

@app.errorhandler(405)
def not_allowed(e):
    return _err("Method Not Allowed", 405)

# ---- local dev entrypoint (Render will *not* run this) ---------------------

if __name__ == "__main__":
    # Local only: python app.py
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)





















































