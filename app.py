# app.py
import os, json, time
from datetime import datetime
from typing import List, Dict, Any
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

# ----- Optional rate limiting (never break deploys)
class _NoopLimiter:
    def __init__(self, *_, **__): pass
    def init_app(self, *_args, **_kwargs): pass
    def limit(self, *_a, **_k):
        def deco(fn): return fn
        return deco

try:
    # pip package: Flask-Limiter ; import name: flask_limiter
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LimiterClass = Limiter
    limiter = LimiterClass(get_remote_address, default_limits=["60/minute"])
except Exception:
    limiter = _NoopLimiter()

# ----- App
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
if hasattr(limiter, "init_app"):
    limiter.init_app(app)

COMMIT = os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# In-memory chat history per visitor (cookie/session-less demo)
# For production, back this with a DB keyed by a real user/session id.
HISTORY: List[Dict[str, Any]] = []

# ----- UI
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# ----- Observability
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}),
            "rule": str(rule),
        })
    table.sort(key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT})

# ----- Models
AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
ACTIVE_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

@app.get("/api/models")
def list_models():
    return jsonify({"active": ACTIVE_MODEL, "available": AVAILABLE_MODELS})

@app.post("/api/model")
@limiter.limit("15/minute")
def set_model():
    global ACTIVE_MODEL
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    if not model:
        return jsonify({"error": "missing_model"}), 400
    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "unknown_model", "allowed": AVAILABLE_MODELS}), 400
    ACTIVE_MODEL = model
    return jsonify({"ok": True, "active": ACTIVE_MODEL})

# ----- Chat API (JSON)
def _dev_echo(user_msg: str) -> str:
    return f"Pong! (dev echo)\nYou said: {user_msg}"

def _openai_chat_sync(message: str, model: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
            {"role": "user", "content": message},
        ],
        temperature=0.6,
    )
    return (resp.choices[0].message.content or "").strip()

@app.post("/api/chat")
@limiter.limit("60/minute")
def api_chat():
    data = request.get_json(force=True, silent=False)
    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "expected_json_with_message"}), 400

    user_msg = str(data.get("message", "")).strip() or "Hello!"
    HISTORY.append({"role": "user", "content": user_msg, "ts": time.time()})

    try:
        if not OPENAI_KEY:
            reply = _dev_echo(user_msg)
        else:
            reply = _openai_chat_sync(user_msg, ACTIVE_MODEL)
        HISTORY.append({"role": "assistant", "content": reply, "ts": time.time()})
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": "upstream_error", "detail": str(e)}), 502

# ----- Stream (Server-Sent Events style over fetch/readable)
@app.post("/api/chat/stream")
@limiter.limit("60/minute")
def chat_stream():
    data = request.get_json(force=True, silent=False)
    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "expected_json_with_message"}), 400
    user_msg = str(data.get("message", "")).strip() or "Hello!"

    # If no key, stream a tiny fake response
    def _fake_stream():
        chunks = ["Thinking", " …", "\nOkay! ", "Here’s ", "your ", "answer."]
        for c in chunks:
            yield c
            time.sleep(0.15)

    if not OPENAI_KEY:
        return app.response_class(_fake_stream(), mimetype="text/plain")

    # Real streaming
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        stream = client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
            stream=True,
        )
        def gen():
            for chunk in stream:
                piece = chunk.choices[0].delta.content or ""
                if piece:
                    yield piece
        return app.response_class(gen(), mimetype="text/plain")
    except Exception as e:
        return jsonify({"error": "upstream_error", "detail": str(e)}), 502

# ----- History API
@app.get("/api/history")
def get_history():
    if not HISTORY:
        return jsonify({"error": "no_conversation"}), 404
    return jsonify({"messages": HISTORY})

@app.get("/api/history/export")
def export_history():
    return jsonify({
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "count": len(HISTORY),
        "messages": HISTORY,
    })
 # ---- Simple stats
START_TS = int(time.time())

@app.get("/api/stats")
def stats():
    total_msgs = sum(len(v) for v in _conversations.values())
    return jsonify({
        "ok": True,
        "since_epoch": START_TS,
        "active_model": _active_model,
        "num_clients": len(_conversations),
        "total_messages": total_msgs,
        "commit": COMMIT,
    })
   

# ----- Static passthrough
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ----- Errors
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






