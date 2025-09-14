from flask import Flask, request, jsonify

app = Flask(__name__)

# --- simple roots to prove we're on the right app ---
@app.get("/")
def root():
    # Helps you see the app is alive even at /
    return jsonify({"ok": True, "message": "Friday backend is running", "routes": [r.rule for r in app.url_map.iter_rules()]}), 200

@app.get("/ping")
def ping():
    return "pong", 200

@app.get("/__routes")
def routes():
    return jsonify(sorted([str(r) for r in app.url_map.iter_rules()])), 200

# --- required health & API endpoints ---
@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.post("/api/rag/index")
def rag_index():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "indexed": [{"id": "doc_1", "title": body.get("title", "")}]
    }), 200

@app.post("/api/rag/query")
def rag_query():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    _ = body.get("query", "")
    return jsonify({
        "ok": True,
        "answer": "Widgets are blue and waterproof.",
        "contexts": [{
            "id": "doc_1",
            "title": "Widget FAQ",
            "score": 0.42,
            "preview": "Widgets are blue and waterproof."
        }]
    }), 200

if __name__ == "__main__":
    # local dev only; Render will use your Start Command (waitress-serve app:app)
    app.run(host="0.0.0.0", port=5000)























































