from __future__ import annotations
import os, json
from datetime import datetime
from flask import Flask, jsonify, render_template, request

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    @app.get("/chat")
    def chat_page():
        return render_template("chat.html")

    @app.get("/ping")
    def ping():
        return jsonify(ok=True, now=datetime.utcnow().isoformat() + "Z")

    # Ultra-minimal echo to prove what the server receives
    @app.post("/api/echo")
    def api_echo():
        body_text = (request.data or b"").decode("utf-8", "ignore")
        return jsonify(
            content_type=request.headers.get("Content-Type", ""),
            is_json=request.is_json,
            json=request.get_json(silent=True),
            form={k: v for k, v in request.form.items()},
            raw_len=len(body_text),
            raw_sample=body_text[:200],
        )

    @app.post("/api/chat")
    def api_chat():
        content_type = request.headers.get("Content-Type", "")
        data = request.get_json(silent=True)

        message = None

        # JSON body
        if isinstance(data, dict):
            for k in ("message", "text", "prompt", "content", "q", "query"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    message = v.strip()
                    break

        # Form fallback
        if not message:
            for k in ("message", "text", "prompt", "content", "q", "query"):
                v = request.form.get(k)
                if v and v.strip():
                    message = v.strip()
                    break

        # Raw body fallback
        if not message and request.data:
            body = request.data.decode("utf-8", "ignore").strip()
            if body:
                if body.startswith("{"):
                    try:
                        raw = json.loads(body)
                        if isinstance(raw, dict):
                            for k in ("message", "text", "prompt", "content", "q", "query"):
                                v = raw.get(k)
                                if isinstance(v, str) and v.strip():
                                    message = v.strip()
                                    break
                    except Exception:
                        pass
                if not message:
                    message = body

        if not message:
            return jsonify({
                "error": "Invalid request: expected JSON with 'message'",
                "received": {
                    "content_type": content_type,
                    "is_json": request.is_json,
                    "json_keys": list(data.keys()) if isinstance(data, dict) else None,
                    "form_keys": list(request.form.keys()),
                    "raw_len": len(request.data or b""),
                    "raw_sample": (request.data or b"")[:160].decode("utf-8", "ignore"),
                }
            }), 400

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or OpenAI is None:
            return jsonify(reply=f"(dev echo) You said: {message}")

        try:
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": message}],
                temperature=0.3,
            )
            reply = resp.choices[0].message.content or ""
            return jsonify(reply=reply)
        except Exception as e:
            return jsonify(error=f"OpenAI error: {e}"), 500
# ==========================
# Debug route for Render env
# ==========================
@app.route("/debug/env")
def debug_env():
    import os
    return {
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "flask_env": os.getenv("FLASK_ENV", "not_set"),
        "other_vars": {k: v for k, v in os.environ.items() if k.startswith("FLASK_")}
    }

    @app.after_request
    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    return app
# ==========================
# Debug helpers (safe to keep)
# ==========================
import os
from flask import jsonify

@app.get("/debug/env")
@app.get("/api/debug/env")
def debug_env():
    return jsonify({
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "flask_env": os.getenv("FLASK_ENV", "not_set"),
    })

@app.get("/__routes")
@app.get("/api/__routes")
def list_routes():
    routes = sorted(str(r.rule) for r in app.url_map.iter_rules())
    return jsonify({"routes": routes})



app = create_app()




































