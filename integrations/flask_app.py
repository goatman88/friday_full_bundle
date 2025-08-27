from flask import Flask, render_template, request, jsonify, session
import os
from datetime import timedelta
from openai import OpenAI

def create_app():
    app = Flask(__name__, template_folder="integrations/templates")
    app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")
    app.permanent_session_lifetime = timedelta(days=14)

    @app.route("/ping")
    def ping():
        return jsonify(ok=True, now="")

    @app.route("/chat")
    def chat_page():
        return render_template("chat.html")

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify(error="Invalid request: expected JSON with 'message'"), 400

        # Load history from session (list of {role, content})
        session.permanent = True
        history = session.get("history", [])

        # No key? dev echo
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            reply = f"(dev echo) You said: {message}"
            # keep the UX consistent even in dev
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            # trim history
            if len(history) > 20:  # 10 turns
                history = history[-20:]
            session["history"] = history
            return jsonify(reply=reply)

        # Real model call
        try:
            client = OpenAI(api_key=api_key)
            # Build prompt with short history + new user msg
            messages = history[-18:] + [{"role": "user", "content": message}]
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.3,
            )
            reply = resp.choices[0].message.content
            # save back
            history = messages + [{"role": "assistant", "content": reply}]
            if len(history) > 20:
                history = history[-20:]
            session["history"] = history
            return jsonify(reply=reply)
        except Exception as e:
            # bubble the exact error so chat UI shows it
            return jsonify(error=f"OpenAI error: {e}"), 500

    @app.route("/api/reset", methods=["POST"])
    def api_reset():
        session.pop("history", None)
        return jsonify(ok=True)

    # Optional: debug/status for the pill
    @app.route("/__meta__/debug")
    def debug():
        return jsonify(env={"openai_key_present": bool(os.getenv("OPENAI_API_KEY"))})

    return app

app = create_app()
































