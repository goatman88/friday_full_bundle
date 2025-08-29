# integrations/flask_app.py
from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

# Create one global app that Gunicorn will import
app = Flask(__name__)

# CORS: allow everything under /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.get("/debug/health")
def health():
    """Simple health endpoint for Render checks."""
    return jsonify(ok=True)

@app.get("/routes")
def list_routes():
    """List all registered routes so you can verify what’s live."""
    rules = []
    for r in app.url_map.iter_rules():
        rules.append({
            "endpoint": r.endpoint,
            "methods": sorted(m for m in r.methods
                              if m in {"GET","POST","PUT","DELETE","PATCH","OPTIONS"}),
            "rule": str(r),
        })
    rules.sort(key=lambda x: x["rule"])
    return jsonify(rules)

@app.post("/api/chat")
def chat():
    """Echo back a message (basic contract test)."""
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "")
    if not isinstance(msg, str):
        return jsonify(error="Expected JSON with key 'message' (string)"), 400
    reply = f"Pong: {msg or 'How can I assist you today?'}"
    return jsonify(reply=reply), 200












































