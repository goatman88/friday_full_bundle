# app.py
import os, json, time, uuid, sqlite3, pathlib
from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_from_directory, abort
from flask_cors import CORS

# limiter.py (snippet to copy into app.py after app=CORS(...))
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
# Per-route example:
# limiter.limit("20/minute")(api_chat)


# ---------------- App setup
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Observability logger
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("friday")

# Flags
COMMIT = os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
ACTIVE_MODEL = {"name": DEFAULT_MODEL}  # mutable holder for /api/model

# Optional: Bearer auth for /api/*
API_KEY = os.getenv("FRIDAY_API_KEY", "").strip()

# ---------------- SQLite persistence
DB_PATH = pathlib.Path("data.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_msg(conv_id: str, role: str, content: str):
    with db() as conn:
        conn.execute("INSERT INTO messages (conv_id,role,content) VALUES (?,?,?)",
                     (conv_id, role, content))

def load_history(conv_id: str, limit: int = 50):
    with db() as conn:
        rows = conn.execute(
            "SELECT role,content,ts FROM messages WHERE conv_id=? ORDER BY id DESC LIMIT ?",
            (conv_id, limit)
        ).fetchall()
    # reverse to oldest -> newest
    return list(reversed([dict(r) for r in rows]))

init_db()

# ---------------- Helpers
def conv_id_from_req() -> str:
    return request.headers.get("X-Conv-Id", request.args.get("conv_id", "default")).strip() or "default"

def require_key():
    if not request.path.startswith("/api/"):
        return
    if not API_KEY:
        return
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token != API_KEY:
        abort(401)

@app.before_request
def _start():
    request._t0 = time.time()
    request._rid = uuid.uuid4().hex[:8]
    require_key()

@app.after_request
def _end(resp):
    try:
        ms = int((time.time() - getattr(request, "_t0", time.time())) * 1000)
        log.info("rid=%s %s %s -> %s %dms",
                 getattr(request, "_rid", "-"),
                 request.method, request.path, resp.status, ms)
    finally:
        return resp

# ---------------- Pages (UI)
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# ---------------- Debug & routing
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET", "POST", "OPTIONS"}),
            "rule": str(rule),
        })
    table = sorted(table, key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "model": ACTIVE_MODEL["name"]})

# ---------------- Models
AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]

@app.get("/api/models")
def list_models():
    return jsonify({"active": ACTIVE_MODEL["name"], "available": AVAILABLE_MODELS})

@app.post("/api/model")
def set_model():
    data = request.get_json(silent=True) or {}
    name = str(data.get("model", "")).strip()
    if name not in AVAILABLE_MODELS:
        return jsonify({"error": "unknown_model", "available": AVAILABLE_MODELS}), 400
    ACTIVE_MODEL["name"] = name
    return jsonify({"ok": True, "active": name})

# ---------------- Chat API (POST)
@app.post("/api/chat")
def api_chat():
    # Expect JSON: { "message": "..." }
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "invalid_json", "hint": "Send JSON body with 'message'"}), 400

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "invalid_json", "hint": "Send JSON body with 'message'"}), 400

    user_msg = str(data.get("message", "")).strip() or "Hello!"
    conv_id = conv_id_from_req()

    # Build history
    history = load_history(conv_id)
    messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_msg})

    # No key -> dev echo so UI still works
    if not OPENAI_KEY:
        reply = f"Hello! (dev echo on)\nYou said: {user_msg}"
        save_msg(conv_id, "user", user_msg)
        save_msg(conv_id, "assistant", reply)
        return jsonify({"reply": reply})

    # Real OpenAI call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=ACTIVE_MODEL["name"],
            messages=messages,
            temperature=0.6,
        )
        text = (resp.choices[0].message.content or "").strip()
        save_msg(conv_id, "user", user_msg)
        save_msg(conv_id, "assistant", text)
        return jsonify({"reply": text})
    except Exception as e:
        return jsonify({"error": "upstream_error", "detail": str(e)}), 502

# ---------------- Streaming (SSE)
@app.get("/api/chat/stream")
def chat_stream():
    user_msg = request.args.get("q", "").strip()
    if not user_msg:
        return jsonify({"error": "missing_q"}), 400
    conv_id = conv_id_from_req()

    # Dev echo path
    if not OPENAI_KEY:
        def gen_echo():
            yield "event: start\ndata: {}\n\n"
            for chunk in ["Hello", " (dev)", " echo"] :
                time.sleep(0.05)
                yield f"data: {chunk}\n\n"
            yield "event: end\ndata: {}\n\n"
        return app.response_class(gen_echo(), mimetype="text/event-stream")

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    history = load_history(conv_id)
    messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_msg})

    def gen():
        yield "event: start\ndata: {}\n\n"
        acc = []
        stream = client.chat.completions.create(
            model=ACTIVE_MODEL["name"],
            messages=messages,
            stream=True,
            temperature=0.6,
        )
        for evt in stream:
            delta = evt.choices[0].delta.content or ""
            if delta:
                acc.append(delta)
                yield f"data: {delta}\n\n"
        text = "".join(acc).strip()
        save_msg(conv_id, "user", user_msg)
        save_msg(conv_id, "assistant", text)
        yield "event: end\ndata: {}\n\n"

    return app.response_class(gen(), mimetype="text/event-stream")

# ---------------- History endpoints
@app.get("/api/history")
def get_history():
    conv_id = conv_id_from_req()
    msgs = load_history(conv_id)
    if not msgs:
        return jsonify({"error": "no_conversation"}), 404
    return jsonify({"messages": [{"role": m["role"], "content": m["content"], "ts": m["ts"]} for m in msgs]})

@app.get("/api/history/export")
def export_history():
    conv_id = conv_id_from_req()
    msgs = load_history(conv_id)
    if not msgs:
        return "No conversation.", 200, {"Content-Type": "text/plain; charset=utf-8"}
    lines = []
    for m in msgs:
        ts = m.get("ts", "")
        lines.append(f"[{ts}] {m['role']}: {m['content']}")
    body = "\n".join(lines)
    return body, 200, {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": f'attachment; filename="history-{conv_id}.txt"',
    }

# ---------------- Static passthrough
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------------- Error handlers
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


# --- Entrypoint --------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)





