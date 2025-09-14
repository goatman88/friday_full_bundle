# app.py
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---- basic/home ----
@app.get("/", endpoint="home")
def home():
    return jsonify({
        "ok": True,
        "message": "Friday service is running.",
        "try": ["/health", "/__routes", "/api/rag/index (POST)", "/api/rag/query (POST)"]
    }), 200

# ---- health ----
@app.get("/health", endpoint="health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

# ---- debug: list routes (no auth) ----
@app.get("/__routes", endpoint="routes")
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != "static":
            routes.append({
                "endpoint": rule.endpoint,
                "rule": str(rule),
                "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            })
    return jsonify({"ok": True, "routes": routes}), 200

# ---- helpers ----
def _authorized(req) -> bool:
    auth = req.headers.get("Authorization", "")
    # accept any non-empty Bearer for now (keeps your tests simple)
    return auth.startswith("Bearer ") and len(auth.split(" ", 1)[1].strip()) > 0

# ---- RAG stubs ----
@app.post("/api/rag/index", endpoint="rag_index")
def rag_index():
    if not _authorized(request):
        return jsonify({"error": "Unauthorized", "ok": False}), 401

    body = request.get_json(silent=True) or {}
    title = body.get("title", "Untitled")
    # pretend to index one doc
    return jsonify({
        "ok": True,
        "indexed": [{"id": "doc_1", "title": title}]
    }), 200

@app.post("/api/rag/query", endpoint="rag_query")
def rag_query():
    if not _authorized(request):
        return jsonify({"error": "Unauthorized", "ok": False}), 401

    body = request.get_json(silent=True) or {}
    query = body.get("query", "")
    topk = int(body.get("topk", 2))

    return jsonify({
        "ok": True,
        "answer": "Widgets are blue and waterproof.",
        "query": query,
        "contexts": [
            {
                "id": "doc_1",
                "title": "Widget FAQ",
                "score": 0.42,
                "preview": "Widgets are blue and waterproof."
            }
        ][:topk]
    }), 200

# (No __main__ block needed on Render; waitress will import app:app)





















































