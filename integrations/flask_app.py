# integrations/flask_app.py
from __future__ import annotations

import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

load_dotenv()

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app = Flask(__name__, template_folder=TEMPLATES_DIR)
CORS(app)


# ---------- helpers ----------
def _safe_env():
    """Return safe env info (no secrets)."""
    return {
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "database_url_present": bool(os.getenv("DATABASE_URL")),
        "FLASK_ENV": os.getenv("FLASK_ENV", "production"),
        "file_loaded": __file__,
    }


def _dev_echo(text: str) -> str:
    if text.strip().lower() == "ping":
        return "Pong! How can I assist you today?"
    return f"Friday: {text}"


def _chat_reply(message: str) -> str:
    """Use OpenAI if key is present; otherwise dev echo."""
    if not os.getenv("OPENAI_API_KEY"):
        return _dev_echo(message)

    try:
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": "You are Friday, a concise, helpful assistant."},
                {"role": "user", "content": message},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        # On any error, fall back so the app keeps working.
        app.logger.exception("OpenAI call failed; falling back to dev echo.")
        return _dev_echo(message)


# ---------- pages ----------
@app.get("/")
def root():
    return render_template("chat.html")


@app.get("/chat")
def chat_page():
    return render_template("chat.html")


# ---------- APIs ----------
@app.post("/api/chat")
def api_chat():
    if not request.is_json:
        return jsonify(error="Invalid request: expected JSON with 'message'"), 400
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")
    if not isinstance(message, str):
        return jsonify(error="Invalid request: expected JSON with 'message'"), 400

    reply = _chat_reply(message)
    return jsonify(reply=reply)


@app.post("/api/echo")
def api_echo():
    return jsonify(received=request.get_json(silent=True) or {})


# --- debug + utility endpoints ---
import os, re
from flask import jsonify

@app.get("/debug/health")
def debug_health():
    return jsonify(ok=True), 200

@app.get("/debug/env")
def debug_env():
    # redact anything that smells like a secret
    safe = {
        k: v
        for k, v in os.environ.items()
        if not re.search(r"(KEY|SECRET|TOKEN|PASS|PWD|PASSWORD|AUTH)", k, re.I)
    }
    extras = {
        "FLASK_ENV": app.config.get("ENV"),
        "FLASK_APP": os.getenv("FLASK_APP"),
        "file_loaded": __file__,
    }
    return jsonify(env=safe, extras=extras), 200

@app.get("/routes")
def list_routes():
    routes = sorted(rule.rule for rule in app.url_map.iter_rules())
    return jsonify(routes=routes), 200


@app.get("/healthz")
def healthz():
    return jsonify(ok=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")




































