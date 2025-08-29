import os
from flask import Flask, request, jsonify
from flask_cors import CORS

APP_FINGERPRINT = os.getenv("RENDER_GIT_COMMIT", "local")[:7]

def build_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.get("/__live__")
    def live():
        return jsonify(service="friday", commit=APP_FINGERPRINT, ok=True)

    @app.get("/debug/health")
    def health():
        return jsonify(ok=True, commit=APP_FINGERPRINT)

    @app.get("/routes")
    def routes():
        rules = []
        for r in app.url_map.iter_rules():
            rules.append({
                "endpoint": r.endpoint,
                "rule": str(r),
                "methods": sorted(m for m in r.methods
                                  if m in {"GET","POST","PUT","PATCH","DELETE","OPTIONS"})
            })
        rules.sort(key=lambda x: x["rule"])
        return jsonify(rules)

    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True) or {}
        msg = data.get("message")
        if not isinstance(msg, str):
            return jsonify(error='expected JSON with "message"'), 400
        return jsonify(reply=f"Pong: {msg}", commit=APP_FINGERPRINT)

    return app

app = build_app()
print(">>> BOOTED app.py with commit:", APP_FINGERPRINT, flush=True)