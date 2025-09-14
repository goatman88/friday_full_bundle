# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.get("/")
def index():
    # helpful landing page so the browser doesn't just show "Not Found"
    return jsonify({
        "ok": True,
        "service": "friday",
        "message": "Try GET /health or POST /api/rag/*"
    }), 200

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.get("/__routes")
def routes():
    """Debug helper to confirm what's registered in production."""
    out = []
    for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        methods = sorted([m for m in r.methods if m not in ("HEAD", "OPTIONS")])
        out.append({"rule": str(r), "methods": methods, "endpoint": r.endpoint})
    return jsonify({"ok": True, "routes": out}), 200

def _check_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or len(auth.split(" ", 1)[1].strip()) == 0:
        return False
    return True

@app.post("/api/rag/index")
def rag_index():
    if not _check_auth():
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    title = body.get("title", "")
    text = body.get("text", "")
    source = body.get("source", "unknown")
    # stubbed indexer
    return jsonify({
        "ok": True,
        "indexed": [{"id": "doc_1", "title": title, "source": source, "chars": len(text)}]
    }), 200

@app.post("/api/rag/query")
def rag_query():
    if not _check_auth():
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    query = body.get("query", "")
    topk = int(body.get("topk", 2))
    # stubbed answer
    return jsonify({
        "ok": True,
        "query": query,
        "answer": "Widgets are blue and waterproof.",
        "contexts": [
            {"id": "doc_1", "title": "Widget FAQ", "score": 0.42,
             "preview": "Widgets are blue and waterproof."}
        ][:topk]
    }), 200

if __name__ == "__main__":
    # local dev only
    import os
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
)





















































