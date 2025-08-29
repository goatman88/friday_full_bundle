# integrations/flask_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS

def create_app() -> Flask:
    app = Flask(__name__)
    # CORS for any /api/* request; open origins for testing
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.get("/debug/health")
    def health():
        return jsonify(ok=True), 200

    @app.get("/routes")
    def list_routes():
        rules = []
        for r in app.url_map.iter_rules():
            if r.endpoint == "static":
                continue
            rules.append({
                "endpoint": r.endpoint,
                "methods": sorted(list(r.methods)),
                "rule": str(r),
            })
        rules.sort(key=lambda x: x["rule"])
        return jsonify(rules), 200

    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True) or {}
        msg = data.get("message")
        if not isinstance(msg, str):
            return jsonify(error="expected JSON with 'message'"), 400
        # simple echo so you can verify POSTs
        return jsonify(reply=f"Pong: {msg}"), 200

    return app

# Expose a concrete app instance so our Procfile can use it
app = create_app()











































