# app.py
import os, json, sqlite3, uuid
from contextlib import closing
from datetime import datetime
from typing import Optional

from flask import (
    Flask, jsonify, request, render_template, send_from_directory,
    session, Response
)
from flask_cors import CORS

# ---------- App setup
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# a secret for cookies/session
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# helpful flags for logs/debug
COMMIT = os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DB_PATH = os.getenv("DB_PATH", "friday.db")

# ---------- rate limit (graceful fallback if package missing)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def make_limiter(app_):
        # memory storage is fine for a single Render instance
        return Limiter(get_remote_address, app=app_, storage_uri="memory://")
except Exception:
    Limiter = None

    def get_remote_address():
        # simple proxy-aware remote address
        return request.headers.get("X-Forwarded-For", request.remote_addr)

    def make_limiter(app_):
        class _Noop:
            def limit(self, *_a, **_k):
                def deco(f): return f
                return deco
        return _Noop()

limiter = make_limiter(app)

# ---------- tiny SQLite helpers
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def bootstrap_db():
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        """)
        conn.commit()

bootstrap_db()

def current_conversation_id() -> str:
    cid: Optional[str] = session.get("conversation_id")
    if not cid:
        cid = uuid.uuid4().hex[:12]
        session["conversation_id"] = cid
        with closing(db()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id, created_at) VALUES (?,?)",
                (cid, now_iso()),
            )
            conn.commit()
    return cid

def save_message(cid: str, role: str, content: str):
    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
            (cid, role, content, now_iso()),
        )
        conn.commit()

# ---------- Model picker (backend)
AVAILABLE_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"
]

def active_model():
    return session.get("model_override") or os.getenv("OPENAI_MODEL", MODEL)

@app.get("/api/models")
def list_models():
    return jsonify({"active": active_model(), "available": AVAILABLE_MODELS})

@app.post("/api/model")
def set_model():
    data = request.get_json(force=True, silent=True) or {}
    name = str(data.get("model", "")).strip()
    if name and name in AVAILABLE_MODELS:
        session["model_override"] = name
        return jsonify({"ok": True, "active": name})
    return jsonify({"error": "invalid_model", "available": AVAILABLE_MODELS}), 400

# ---------- Pages (UI)
@app.get("/")
def home():
    # Landing -> serve chat UI
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    # Explicit /chat route
    return render_template("chat.html", title="Friday AI")

# ---------- Observability
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            # keep static record tidy
            rule_str = "/static/<path:filename>"
        else:
            rule_str = str(rule)
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}),
            "rule": rule_str,
        })
    table = sorted(table, key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT})

# ---------- API: Chat
def openai_client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY", OPENAI_KEY)
    return OpenAI(api_key=key)

@limiter.limit("15/minute")
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
    cid = current_conversation_id()
    save_message(cid, "user", user_msg)

    # If no key, friendly echo so UI/dev tests still work
    if not OPENAI_KEY:
        reply = f"Hello there! 😊\n\n(dev echo) You said: {user_msg}"
        save_message(cid, "assistant", reply)
        return jsonify({"reply": reply}), 200

    # Real OpenAI call
    try:
        client = openai_client()
        resp = client.chat.completions.create(
            model=active_model(),
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            text = "I didn’t receive a completion, but I’m here and listening."
        save_message(cid, "assistant", text)
        return jsonify({"reply": text}), 200
    except Exception as e:
        # keep UI alive; surface error text
        detail = str(e)
        save_message(cid, "assistant", f"[upstream_error] {detail}")
        return jsonify({"error": "upstream_error", "detail": detail}), 502

# ---------- History: export JSON
@app.get("/api/history/export")
def export_history():
    cid = session.get("conversation_id")
    if not cid:
        return jsonify({"error": "no_conversation"}), 400
    with closing(db()) as conn:
        convo = conn.execute(
            "SELECT id, created_at FROM conversations WHERE id=?", (cid,)
        ).fetchone()
        msgs = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY created_at",
            (cid,),
        ).fetchall()
    payload = {
        "conversation": dict(convo) if convo else {"id": cid, "created_at": None},
        "messages": [dict(m) for m in msgs],
        "exported_at": now_iso(),
        "model": active_model(),
        "commit": COMMIT,
    }
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{cid}.json"'
        },
    )

# ---------- Static passthrough (optional)
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- API-friendly errors
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

# ---------- Local dev
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)




