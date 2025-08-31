# app.py
import os, json, time, secrets
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import (
    Flask, jsonify, request, send_from_directory,
    Response
)
from flask_cors import CORS

# ---------- App & config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*")

# ---------- Redis (persistent history, tokens, prefs) ----------
# Set REDIS_URL in your environment (Render: "redis://default:<password>@<host>:6379/0")
r = None
try:
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        import redis  # pip install redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as _e:
    r = None  # keep running without Redis

def now_ts() -> float:
    return time.time()

def redis_ok() -> bool:
    if not r:
        return False
    try:
        r.ping()
        return True
    except Exception:
        return False

# ---------- Keys & helpers ----------
def k_history(username: str) -> str:
    return f"hist:{username}"

def k_model_active() -> str:
    return "model:active"

def k_user_model(username: str) -> str:
    return f"user:{username}:model"

def k_admin_code(code: str) -> str:
    return f"admin:code:{code}"

def k_user_authed(username: str) -> str:
    return f"user:{username}:authed"

def active_model(username: Optional[str] = None) -> str:
    # User-specific active model -> global
    if r:
        if username:
            m = r.get(k_user_model(username))
            if m:
                return m
        m = r.get(k_model_active())
        if m:
            return m
    return DEFAULT_MODEL

def set_active_model(model: str, username: Optional[str] = None) -> str:
    if r:
        if username:
            r.set(k_user_model(username), model, ex=60 * 60 * 24 * 30)  # 30 days
        else:
            r.set(k_model_active(), model)
    global DEFAULT_MODEL
    DEFAULT_MODEL = model
    return model

def append_history(username: str, message: str, reply: str) -> None:
    if not r:
        return
    entry = {
        "ts": now_ts(),
        "username": username,
        "message": message,
        "reply": reply,
    }
    r.rpush(k_history(username), json.dumps(entry))
    r.ltrim(k_history(username), -500, -1)  # keep last 500

def get_history(username: str, limit: int = 200) -> List[Dict[str, Any]]:
    if not r:
        return []
    entries = r.lrange(k_history(username), max(-limit, -500), -1)
    out: List[Dict[str, Any]] = []
    for raw in entries:
        try:
            out.append(json.loads(raw))
        except Exception:
            pass
    return out

# ---------- Pages ----------
@app.get("/")
def home():
    # Serve the pretty chat page from /static/chat.html
    return send_from_directory(app.static_folder, "chat.html")

@app.get("/chat")
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")

# ---------- Diagnostics ----------
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}),
            "rule": str(rule),
        })
    table = sorted(table, key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    return jsonify({
        "ok": True,
        "commit": COMMIT,
        "redis": redis_ok(),
        "model": active_model()
    })

# ---------- Models ----------
@app.get("/api/models")
def list_models():
    available = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "o3-mini",
    ]
    username = request.args.get("username") or "guest"
    return jsonify({
        "active": active_model(username),
        "available": available
    })

@app.post("/api/model")
def set_model():
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    username = str(data.get("username") or "guest")
    if not model:
        return jsonify({"error": "missing_model"}), 400
    set_active_model(model, username=None)  # global; change to username=username for per-user
    return jsonify({"active": active_model()})

# ---------- Chat ----------
def openai_reply(model: str, message: str) -> str:
    """
    Use OpenAI if a key is present; otherwise return a friendly echo.
    """
    if not OPENAI_KEY:
        return f"(dev echo) You said: {message}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be concise, friendly, and helpful."},
                {"role": "user", "content": message}
            ],
            temperature=0.6,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[upstream_error] {e}"

@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = str(data.get("message", "")).strip()
    username = str(data.get("username") or "guest")
    model = str(data.get("model") or active_model(username))

    if not message:
        return jsonify({"error": "missing_message"}), 400

    reply = openai_reply(model, message)
    append_history(username, message, reply)
    return jsonify({"reply": reply})

# Optional: a tiny text/event-stream endpoint (SSE) that streams the final reply in two chunks,
# so the UI can demo "streaming" without complex upstream.
@app.get("/api/chat/stream")
def api_chat_stream():
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message:
        return jsonify({"error": "missing_message"}), 400

    text = openai_reply(model, message)

    def gen():
        # basic SSE format
        half = max(1, len(text) // 2)
        yield f"data: {json.dumps({'delta': text[:half]})}\n\n"
        time.sleep(0.15)
        yield f"data: {json.dumps({'delta': text[half:]})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    append_history(username, message, text)
    return Response(gen(), mimetype="text/event-stream")

# ---------- History ----------
@app.get("/api/history")
def get_history_api():
    username = request.args.get("username") or "guest"
    items = get_history(username, limit=int(request.args.get("limit") or 200))
    return jsonify(items)

@app.get("/api/history/export")
def export_history():
    username = request.args.get("username") or "guest"
    items = get_history(username, limit=1000)
    payload = json.dumps(items, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="history_{username}.json"'
        }
    )

# ---------- Admin: mint & redeem ----------
def require_admin(req) -> bool:
    if not ADMIN_TOKEN:
        return False
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    bearer = auth.split(" ", 1)[1].strip()
    return secrets.compare_digest(bearer, ADMIN_TOKEN)

@app.post("/api/admin/mint")
def admin_mint():
    if not require_admin(request):
        return jsonify({"error": "unauthorized"}), 401
    if not r:
        return jsonify({"error": "redis_unavailable"}), 503

    data = request.get_json(silent=True) or {}
    count = int(data.get("count") or 1)
    count = max(1, min(count, 20))

    tokens: List[str] = []
    for _ in range(count):
        code = secrets.token_urlsafe(8)
        # valid for 24h, single-use
        r.set(k_admin_code(code), "1", ex=60*60*24)
        tokens.append(code)

    return jsonify({"tokens": tokens, "ttl_hours": 24})

@app.post("/api/auth/redeem")
def auth_redeem():
    if not r:
        return jsonify({"error": "redis_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip()
    username = str(data.get("username") or "guest")
    if not code:
        return jsonify({"error": "missing_code"}), 400

    key = k_admin_code(code)
    if not r.get(key):
        return jsonify({"success": False, "reason": "invalid_or_expired"}), 400

    # consume code
    r.delete(key)
    r.set(k_user_authed(username), "1", ex=60*60*24*30)  # mark authed for 30d
    return jsonify({"success": True, "user": username})

# ---------- Static passthrough ----------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- API-friendly errors ----------
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

















