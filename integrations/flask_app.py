# integrations/flask_app.py
from __future__ import annotations
import os, json, logging
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.get("/debug/health")
def health():
    return jsonify(ok=True)

@app.get("/routes")
def list_routes():
    routes = []
    for r in app.url_map.iter_rules():
        methods = sorted(m for m in r.methods if m in {"GET","POST","PUT","DELETE"})
        routes.append({"rule": str(r), "endpoint": r.endpoint, "methods": methods})
    # also log to stdout so you can see it in Render logs
    app.logger.info("ROUTES: %s", json.dumps(routes))
    return jsonify(routes)

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=False, force=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify(error="Invalid request: expected JSON with 'message'"), 400
    # dev echo / fallback
    return jsonify(reply="Pong! How can I assist you today?")

# Optional local run (Render uses gunicorn)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)






































