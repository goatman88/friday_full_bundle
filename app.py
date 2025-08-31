import os
import secrets
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

# ------------------------
# App Setup
# ------------------------
app = Flask(__name__, static_folder="static")
CORS(app)

# In-memory stores (simple demo, not production-safe)
HISTORY = []
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", secrets.token_hex(16))  # Set one in env or auto-generate
ACTIVE_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ------------------------
# Basic Routes
# ------------------------
@app.route("/")
def home():
    return jsonify({"message": "Friday AI backend is running 🚀"})

@app.route("/debug/health")
def health():
    return jsonify({"status": "ok", "active_model": ACTIVE_MODEL})

@app.route("/routes")
def list_routes():
    rules = []
    for r in app.url_map.iter_rules():
        rules.append({"endpoint": r.endpoint, "methods": list(r.methods), "rule": str(r)})
    return jsonify(rules)

# ------------------------
# Chat Endpoint
# ------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(force=True)
    message = body.get("message", "")
    user = body.get("username", "guest")

    # Fake AI response (replace with OpenAI call)
    reply = f"Echo from {ACTIVE_MODEL}: {message}"

    # Save to history
    HISTORY.append({
        "user": user,
        "message": message,
        "reply": reply,
        "ts": datetime.utcnow().isoformat()
    })

    return jsonify({"reply": reply})

# ------------------------
# History Endpoints
# ------------------------
@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(HISTORY or {"error": "no_conversation"})

@app.route("/api/history/export", methods=["GET"])
def export_history():
    return jsonify({"exported": HISTORY})

# ------------------------
# Model Management
# ------------------------
@app.route("/api/model", methods=["POST"])
def set_model():
    global ACTIVE_MODEL
    body = request.get_json(force=True)
    model = body.get("model")
    if not model:
        return jsonify({"error": "missing model"}), 400
    ACTIVE_MODEL = model
    return jsonify({"active": ACTIVE_MODEL})

@app.route("/api/models", methods=["GET"])
def list_models():
    return jsonify({
        "active": ACTIVE_MODEL,
        "available": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
    })

# ------------------------
# Admin Endpoints
# ------------------------
@app.route("/api/admin/mint", methods=["POST"])
def mint_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    bearer = auth_header.replace("Bearer ", "").strip()
    if bearer != ADMIN_TOKEN:
        return jsonify({"error": "Forbidden"}), 403

    body = request.get_json(force=True)
    count = body.get("count", 1)

    # Generate N tokens
    tokens = [secrets.token_hex(16) for _ in range(count)]
    return jsonify({"tokens": tokens})

@app.route("/api/auth/redeem", methods=["POST"])
def redeem_token():
    body = request.get_json(force=True)
    code = body.get("code")
    username = body.get("username")

    if not code or not username:
        return jsonify({"error": "Missing fields"}), 400

    # For now just echo back
    return jsonify({"success": True, "user": username, "token": code})

# ------------------------
# Static Files (chat.html, etc.)
# ------------------------
@app.route("/chat")
def chat_page():
    return send_from_directory("static", "chat.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# ------------------------
# Run Local
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
















