# integrations/flask_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.get("/debug/health")
def health():
    return jsonify(ok=True)

@app.get("/routes")
def list_routes():
    rules = []
    for r in app.url_map.iter_rules():
        rules.append({
            "endpoint": r.endpoint,
            "methods": sorted([m for m in r.methods if m in {"GET","POST","PUT","DELETE","PATCH","OPTIONS"}]),
            "rule": str(r)
        })
    # stable order helps visually
    rules.sort(key=lambda x: x["rule"])
    return jsonify(rules)

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = data.get("message")
    if not isinstance(msg, str):
        return jsonify(error="expected JSON with 'message'"), 400
    # simple echo so you can smoke-test from PowerShell
    return jsonify(reply=f"Pong! How can I assist you today?"), 200

if __name__ == "__main__":
    # Handy for local runs: python integrations/flask_app.py
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))








































