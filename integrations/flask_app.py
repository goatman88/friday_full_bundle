from __future__ import annotations
import os
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

try:
    # OpenAI ≥ 1.0 client (no proxies kwarg)
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    # ---------- pages ----------
    @app.route("/chat")
    def chat_page():
        # bump a cache-busting query if you want: ?v=6
        return render_template("chat.html")

    # ---------- health ----------
    @app.route("/ping")
    def ping():
        return jsonify(ok=True, now=datetime.utcnow().isoformat() + "Z")

    # optional: tiny debug endpoint the UI can read (no secrets)
    @app.route("/__meta__/debug")
    def debug_meta():
        return jsonify(
            env={
                "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
                "flask_env": os.getenv("FLASK_ENV", ""),
            }
        )

    # ---------- API ----------
    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        # ensure JSON and the right key
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return (
                jsonify(error="Invalid request: expected JSON with 'message'"),
                400,
            )

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        # Dev echo if no key or no OpenAI library
        if not api_key or OpenAI is None:
            return jsonify(reply=f"(dev echo) You said: {message}")

        # Real call
        try:
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": message}],
                temperature=0.3,
            )
            reply = resp.choices[0].message.content or ""
            return jsonify(reply=reply)
        except Exception as e:
            # Return the error text so the front-end shows it
            return jsonify(error=f"OpenAI error: {e}"), 500

    return app


# Flask CLI entrypoint expects an "app" object
app = create_app()

































