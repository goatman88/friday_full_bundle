# app.py
import os
from datetime import datetime
from flask import Flask, request, jsonify

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
API_TOKEN_ENV = "API_TOKEN"          # set in Render (or accept any token if unset)
SERVICE_NAME  = os.getenv("RENDER_SERVICE_NAME", "friday")
REQUIRE_TOKEN = bool(os.getenv(API_TOKEN_ENV))  # only enforce if you set API_TOKEN

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = Flask(__name__)

def _json_error(status: int, message: str):
    return jsonify({"ok": False, "error": message, "status_code": status}), status

def _auth_ok(req: request) -> bool:
    if not REQUIRE_TOKEN:
        return True
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    return token == os.getenv(API_TOKEN_ENV)

# -----------------------------------------------------------------------------
# Health / basic
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return jsonify({
        "ok": True,
        "service": SERVICE_NAME,
        "message": "Service is up. Try /health, /__routes, /api/rag/index, /api/rag/query."
    }), 200

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "token_required": REQUIRE_TOKEN
    }), 200

@app.get("/ping")
def ping():
    return jsonify({"ok": True, "pong": True}), 200

# Helpful introspection route for troubleshooting 404s you were seeing
@app.get("/__routes")
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            "rule": str(rule)
        })
    return jsonify({"ok": True, "routes": routes}), 200

# -----------------------------------------------------------------------------
# RAG stubs (token-protected if API_TOKEN is set)
# -----------------------------------------------------------------------------
@app.post("/api/rag/index")
def rag_index():
    if not _auth_ok(request):
        return _json_error(401, "Unauthorized")
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    text  = str(body.get("text", "")).strip()
    source = str(body.get("source", "")).strip()

    # Minimal no-op indexer (stub)
    doc_id = "doc_1"
    return jsonify({
        "ok": True,
        "indexed": [{"id": doc_id, "title": title, "source": source, "size": len(text)}]
    }), 200

@app.post("/api/rag/query")
def rag_query():
    if not _auth_ok(request):
        return _json_error(401, "Unauthorized")
    body = request.get_json(silent=True) or {}
    query = str(body.get("query", "")).strip()
    topk  = int(body.get("topk", 2) or 2)

    # Minimal deterministic answer + fake contexts (stub)
    answer = "Widgets are blue and waterproof."
    contexts = [{
        "id": "doc_1",
        "title": "Widget FAQ",
        "score": 0.42,
        "preview": "Widgets are blue and waterproof."
    }][:max(1, topk)]

    return jsonify({"ok": True, "answer": answer, "query": query, "contexts": contexts}), 200

# Optional echo to help debug payloads from PowerShell/cURL
@app.post("/api/rag/echo")
def rag_echo():
    if not _auth_ok(request):
        return _json_error(401, "Unauthorized")
    return jsonify({"ok": True, "headers": dict(request.headers), "json": request.get_json(silent=True)}), 200

# -----------------------------------------------------------------------------
# Error handlers (JSON all the things)
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_e):
    return _json_error(404, "Not Found")

@app.errorhandler(405)
def method_not_allowed(_e):
    return _json_error(405, "Method Not Allowed")

@app.errorhandler(500)
def internal_error(_e):
    return _json_error(500, "Internal Server Error")

# -----------------------------------------------------------------------------
# Local dev entrypoint (Render uses waitress-serve with app:app)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)





















































