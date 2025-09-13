import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, abort

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Flask(__name__)

# In-memory toy store for "indexed" notes (survives while process is running)
INDEX = []

API_TOKEN = os.getenv("API_TOKEN", "").strip()

def require_auth():
    """Simple bearer token check used by protected routes."""
    auth = request.headers.get("Authorization", "")
    if not API_TOKEN:
        abort(500, description="Server missing API_TOKEN")
    if not auth.startswith("Bearer "):
        abort(401, description="Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        abort(401, description="Invalid token")

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
def health():  # endpoint name is 'health' (once!)
    """Public health endpoint."""
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": bool(API_TOKEN),
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }), 200

@app.get("/__routes")
def list_routes():
    """Protected route list (requires Authorization: Bearer <API_TOKEN>)."""
    require_auth()
    out = []
    for rule in app.url_map.iter_rules():
        # Skip static to keep output tidy
        if rule.endpoint == "static":
            continue
        out.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","PUT","DELETE","PATCH"}),
            "rule": str(rule),
        })
    return jsonify({"ok": True, "routes": out}), 200

@app.post("/api/rag/index")
def rag_index():
    """Index a 'note' – very simple stub for testing."""
    require_auth()
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    title = (payload.get("title") or "").strip()
    text  = (payload.get("text")  or "").strip()
    if not title or not text:
        return jsonify({"ok": False, "error": "Both 'title' and 'text' are required"}), 400

    doc_id = f"doc_{int(datetime.now().timestamp()*1000)}"
    INDEX.append({"id": doc_id, "title": title, "text": text})
    return jsonify({"ok": True, "indexed": doc_id, "title": title, "chars": len(text)}), 200

@app.post("/api/rag/query")
def rag_query():
    """Query 'indexed' notes – simple substring scorer for testing."""
    require_auth()
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    q = (payload.get("query") or "").strip()
    topk = int(payload.get("topk") or 2)
    if not q:
        return jsonify({"ok": False, "error": "Field 'query' is required"}), 400

    scored = []
    for d in INDEX:
        score = 1.0 if q.lower() in d["text"].lower() else 0.0
        if score > 0.0:
            scored.append({
                "id": d["id"],
                "title": d["title"],
                "preview": d["text"][:120],
                "score": round(score, 4),
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    contexts = scored[:topk]

    # Friendly answer string like you saw earlier
    answer = " | ".join([c["preview"] for c in contexts]) or "(no matches)"
    return jsonify({"ok": True, "answer": answer, "contexts": contexts}), 200

# -----------------------------------------------------------------------------
# Entrypoint (Render uses WSGI; this is still fine for local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Default PORT for local dev. Render injects PORT env var automatically.
    port = int(os.getenv("PORT", "5000"))
    # 0.0.0.0 so it binds in containers; debug from env if you want
    app.run(host="0.0.0.0", port=port, debug=bool(os.getenv("FLASK_DEBUG")))






















































