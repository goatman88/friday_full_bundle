# app.py  (root)
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI

APP_FINGERPRINT = os.getenv("RENDER_GIT_COMMIT", "local")[:7]

# tell Flask where templates live (you already have chat.html there)
app = Flask(
    __name__,
    template_folder="integrations/templates",
    static_folder="static",
)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- tiny health & introspection helpers ---
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
            "methods": sorted([m for m in r.methods if m in {"GET","POST","PUT","PATCH","DELETE","OPTIONS"}]),
            "rule": str(r),
        })
    rules.sort(key=lambda x: x["rule"])
    return jsonify(rules)

# simple page to try the chat UI in the browser
@app.get("/")
def home():
    return render_template("chat.html")

# --- REAL chat endpoint backed by OpenAI ---
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify(error="Missing 'message'"), 400

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Friday, a helpful assistant."},
                {"role": "user", "content": msg},
            ],
        )
        reply = resp.choices[0].message.content
        return jsonify(reply=reply)
    except Exception as e:
        # Bubble a readable error to the client
        return jsonify(error=str(e)), 500
