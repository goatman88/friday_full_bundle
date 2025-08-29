# integrations/flask_app.py
from __future__ import annotations
from flask import Flask, jsonify, request

def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/debug/health")
    def health():
        return jsonify(ok=True), 200

    @app.get("/routes")
    def list_routes():
        rules = []
        for r in app.url_map.iter_rules():
            rules.append({
                "endpoint": r.endpoint,
                "methods": sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}),
                "rule": str(r)
            })
        return jsonify(rules), 200

    @app.post("/api/chat")
    def chat():
        try:
            body = request.get_json(force=True, silent=True) or {}
            msg = str(body.get("message", "")).strip() or "ping"
            # echo
            return jsonify(reply=f"Pong! You said: {msg}"), 200
        except Exception as e:
            return jsonify(error=str(e)), 400

    # ---- print URL map on boot so Render logs show routes ----
    @app.before_first_request
    def _print_routes():
        app.logger.info("==== Registered routes ====")
        for r in app.url_map.iter_rules():
            app.logger.info("rule=%s  methods=%s  endpoint=%s",
                            r.rule, sorted(m for m in r.methods if m not in {"HEAD","OPTIONS"}), r.endpoint)
        app.logger.info("================================")

    return app

# Gunicorn can import either `app` OR call factory.
# Expose `app` for `integrations.flask_app:app`
app = create_app()










































