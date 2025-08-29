import os
from flask import Flask, request, jsonify
from flask_cors import CORS

APP_FINGERPRINT = os.getenv("RENDER_GIT_COMMIT", "local")[:7]

def build_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Liveness probe (Render hits HEAD /, you'll also have this GET endpoint)
    @app.get("/debug/health")
    def health():
        return jsonify(ok=True, commit=APP_FINGERPRINT)

    # See what routes are registered
    @app.get("/routes")
    def list_routes():
        rules = []
        for r in app.url_map.iter_rules():
            rules.append({
                "endpoint": r.endpoint,
                "methods": sorted([m for m in r.methods if m in {"GET","POST","PUT","PATCH","DELETE","OPTIONS"}]),
                "rule": str(r),
            })
        rules.sort(key=lambda x: x["rule"])
        return jsonify(rules)

    # Simple echo to test POST/JSON quickly
    @app.post("/api/echo")
    def echo():
        payload = request.get_json(silent=True) or {}
        return jsonify(received=payload)

    # Your chat stub (returns a canned reply so you can verify end-to-end)
    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True) or {}
        msg = data.get("message")
        if not isinstance(msg, str):
            return jsonify(error="expected JSON with 'message'"), 400
        return jsonify(reply=f"Pong: {msg}", commit=APP_FINGERPRINT)

    return app

# 🔴 The critical line Render needs:
app = build_app()

