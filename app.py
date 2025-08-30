# app.py
import os, time
from flask import Flask, jsonify, request, render_template, send_from_directory, session

from flask_cors import CORS

# -------- App setup
app = Flask(__name__, static_folder="static", template_folder="templates")

# session for per-user history; set on Render in env, has a dev fallback
app.secret_key = os.getenv("SECRET_KEY", os.urandom(16).hex())

CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", ""))
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# -------- Pages (UI)
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# -------- Small observability helpers
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","DELETE","OPTIONS"}),
            "rule": str(rule),
        })
    table = sorted(table, key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT})

# -------- API: model info
@app.get("/api/model")
def api_model():
    return jsonify({"model": MODEL, "has_key": bool(OPENAI_KEY)})

# -------- API: chat history (session-backed)
@app.get("/api/history")
def get_history():
    return jsonify(session.get("history", []))

@app.delete("/api/history")
def clear_history():
    session["history"] = []
    return jsonify({"ok": True})

def _push_history(role, content):
    hist = session.get("history", [])
    hist.append({"role": role, "content": content, "ts": int(time.time())})
    session["history"] = hist

# -------- API: Chat
@app.post("/api/chat")
def api_chat():
    # Expect JSON: { "message": "..." }
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    user_msg = str(data.get("message", "")).strip() or "Hello!"
    _push_history("user", user_msg)

    # If no OPENAI_API_KEY, reply with a friendly dev echo so the UI still works
    if not OPENAI_KEY:
        reply = f"Pong! (dev echo)\n\nYou said: {user_msg}"
        _push_history("assistant", reply)
        return jsonify({"reply": reply}), 200

    # Real OpenAI call (openai>=1.x)
    try:
        from openai import OpenAI
        client = OpenAI()  # reads OPENAI_API_KEY from env
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", MODEL),
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            text = "…(empty reply from upstream)"
        _push_history("assistant", text)
        return jsonify({"reply": text}), 200

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        _push_history("assistant", f"(upstream error)\n{err}")
        return jsonify({"error": "upstream_error", "detail": err}), 502

# -------- Static passthrough (optional)
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# -------- Friendly errors (nicer JSON for API callers)
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "path": request.path}), 404
    return "Not Found", 404

@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "method_not_allowed", "path": request.path}), 405
    return "Method Not Allowed", 405

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


