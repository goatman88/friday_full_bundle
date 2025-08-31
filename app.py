# app.py
import os, json, time, secrets
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator

from flask import (
    Flask, jsonify, request, send_from_directory,
    Response, stream_with_context
)
from flask_cors import CORS

# ---------- App & config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ---------- Redis (persistent history, tokens) ----------
r = None
try:
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        import redis  # requires redis>=5
        r = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    r = None

def redis_ok() -> bool:
    if not r: return False
    try: r.ping(); return True
    except Exception: return False

# ---------- Key helpers ----------
def k_history(username: str) -> str: return f"hist:{username}"
def k_model_active() -> str: return "model:active"
def k_user_model(username: str) -> str: return f"user:{username}:model"
def k_admin_code(code: str) -> str: return f"admin:code:{code}"
def k_user_authed(username: str) -> str: return f"user:{username}:authed"

def active_model(username: Optional[str] = None) -> str:
    if r:
        if username:
            m = r.get(k_user_model(username))
            if m: return m
        m = r.get(k_model_active())
        if m: return m
    return DEFAULT_MODEL

def set_active_model(model: str, username: Optional[str] = None) -> str:
    if r:
        if username:
            r.set(k_user_model(username), model, ex=60*60*24*30)
        else:
            r.set(k_model_active(), model)
    global DEFAULT_MODEL
    DEFAULT_MODEL = model
    return model

def append_history(username: str, message: str, reply: str) -> None:
    if not r: return
    entry = {
        "ts": time.time(),
        "username": username,
        "message": message,
        "reply": reply,
    }
    r.rpush(k_history(username), json.dumps(entry))
    r.ltrim(k_history(username), -500, -1)

def get_history(username: str, limit: int = 200) -> List[Dict[str, Any]]:
    if not r: return []
    entries = r.lrange(k_history(username), max(-limit, -500), -1)
    out = []
    for raw in entries:
        try: out.append(json.loads(raw))
        except Exception: pass
    return out

# ---------- Pages ----------
@app.get("/")
def home():
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
    available = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
    username = request.args.get("username") or "guest"
    return jsonify({"active": active_model(username), "available": available})

@app.post("/api/model")
def set_model_api():
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    if not model:
        return jsonify({"error": "missing_model"}), 400
    set_active_model(model, username=None)  # global set; switch to per-user if you prefer
    return jsonify({"active": active_model()})

# ---------- Chat (non-streaming fallback) ----------
def openai_nonstream_reply(model: str, message: str) -> str:
    if not OPENAI_KEY:
        return f"(dev echo) {message}"
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
    reply = openai_nonstream_reply(model, message)
    append_history(username, message, reply)
    return jsonify({"reply": reply})

# ---------- Chat (STREAMING over SSE) ----------
def sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def stream_openai(model: str, message: str) -> Generator[str, None, str]:
    """
    Yield SSE chunks with {"delta": "..."} as tokens arrive.
    Return final text so we can store history.
    """
    final_text = []
    if not OPENAI_KEY:
        # Dev echo streamer: type it out slowly
        demo = f"(dev echo) {message}"
        for ch in demo:
            final_text.append(ch)
            yield sse_event({"delta": ch})
            time.sleep(0.01)
        yield sse_event({"done": True})
        return "".join(final_text)

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be concise, friendly, and helpful."},
                {"role": "user", "content": message}
            ],
            temperature=0.6,
            stream=True,
        )
        last_heartbeat = time.time()
        for chunk in stream:  # yields ChatCompletionChunk
            # heartbeat every ~10s so proxies don’t cut us off
            if time.time() - last_heartbeat > 10:
                yield ":keepalive\n\n"
                last_heartbeat = time.time()

            part = ""
            try:
                part = chunk.choices[0].delta.content or ""
            except Exception:
                part = ""
            if part:
                final_text.append(part)
                yield sse_event({"delta": part})
        yield sse_event({"done": True})
        return "".join(final_text)
    except Exception as e:
        # Emit an error event so the UI can show it
        yield sse_event({"error": str(e)})
        yield sse_event({"done": True})
        return f"[upstream_error] {e}"

@app.get("/api/chat/stream")
def api_chat_stream():
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message:
        return jsonify({"error": "missing_message"}), 400

    @stream_with_context
    def generate():
        text_collected = ""
        for chunk in stream_openai(model, message):
            yield chunk
            # capture final once generator returns (we can't read return value here)
            if '"done": true' in chunk:
                # best-effort; we’ll rebuild from previous deltas in UI, but store echo/nonstream for safety
                pass
        # As a fallback, also append non-stream reply to history (ensures something is saved)
        # If you want perfection, refactor stream_openai to send final text via a terminal event and capture it in UI to POST /api/history/append.
        nonstream = openai_nonstream_reply(model, message)
        append_history(username, message, nonstream)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), headers=headers)

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
    payload = json.dumps(items, indent=2, ensure_ascii=False)
    return Response(
        payload, mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="history_{username}.json"'}
    )

# ---------- Admin: mint & redeem ----------
def require_admin(req) -> bool:
    if not ADMIN_TOKEN: return False
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return False
    bearer = auth.split(" ", 1)[1].strip()
    return secrets.compare_digest(bearer, ADMIN_TOKEN)

@app.post("/api/admin/mint")
def admin_mint():
    if not require_admin(request):
        return jsonify({"error": "unauthorized"}), 401
    if not r:
        return jsonify({"error": "redis_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    count = max(1, min(int(data.get("count") or 1), 20))
    tokens: List[str] = []
    for _ in range(count):
        code = secrets.token_urlsafe(8)
        r.set(k_admin_code(code), "1", ex=60*60*24)  # 24h
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
    r.delete(key)
    r.set(k_user_authed(username), "1", ex=60*60*24*30)
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
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)


















