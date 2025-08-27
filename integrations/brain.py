# integrations/brain.py
from __future__ import annotations
import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

bp = Blueprint("ai", __name__)

# ---------- UI ----------
@bp.get("/chat")
def chat_page():
    return render_template("chat.html")

# ---------- quick JSON sanity-check ----------
@bp.post("/api/echo")
def api_echo():
    payload = request.get_json(silent=True)
    if not payload or "message" not in payload:
        return jsonify(error="Invalid request: expected JSON with 'message'", got=payload), 400
    return jsonify(reply=f"(echo) {payload['message']}")

# ---------- main chat endpoint ----------
@bp.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True)
    if not payload or "message" not in payload:
        return jsonify(error="Invalid request: expected JSON with 'message'", got=payload), 400

    user_msg = str(payload["message"]).strip()[:4000]  # basic guard

    # 1) No key → dev echo
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify(
            reply=f"(dev echo) You said: {user_msg}",
            model="dev",
            at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        ), 200

    # 2) With key → real model
    try:
        # OpenAI SDK v1
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are Friday, a concise, helpful personal AI."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        return jsonify(
            reply=reply,
            model="openai",
            at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        ), 200

    except Exception as e:
        # Always JSON on errors too
        return jsonify(error=f"Model error: {type(e).__name__}: {e}"), 500












