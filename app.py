# app.py
import os, json, time, uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import (
    Flask, jsonify, request, render_template, send_from_directory, Response
)
from flask_cors import CORS

# ---------------- App
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
ACTIVE_MODEL = DEFAULT_MODEL if DEFAULT_MODEL in AVAILABLE_MODELS else "gpt-4o-mini"

# ---------------- Optional Redis persistence (falls back to memory)
_redis = None
try:
    from redis import Redis
    if os.getenv("REDIS_URL"):
        _redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
except Exception:
    _redis = None  # fine, we’ll just use memory

def _rkey(cid: str) -> str:
    return f"conv:{cid}"

def _load_thread(cid: str) -> List[Dict[str, Any]]:
    if _redis:
        raw = _redis.get(_rkey(cid))
        return json.loads(raw) if raw else []
    return _conversations.get(cid, [])

def _save_thread(cid: str, msgs: List[Dict[str, Any]]) -> None:
    if _redis:
        _redis.set(_rkey(cid), json.dumps(msgs))
    else:
        _conversations[cid] = msgs

def _delete_thread(cid: str) -> None:
    if _redis:
        _redis.delete(_rkey(cid))
    else:
        _conversations.pop(cid, None)

def _all_cids() -> List[str]:
    if _redis:
        cids: List[str] = []
        cursor = 0
        while True:
            cursor, keys = _redis.scan(cursor=cursor, match="conv:*", count=500)
            cids.extend([k.split(":", 1)[1] for k in keys])
            if cursor == 0:
                break
        return cids
    return list(_conversations.keys())

# in-memory fallback
_conversations: Dict[str, List[Dict[str, Any]]] = {}

# ---------------- Optional rate limiting (auto if installed)
_limiter = None
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
except Exception:
    _limiter = None

def limit(rule: str):
    def deco(fn):
        if _limiter:
            return _limiter.limit(rule)(fn)
        return fn
    return deco

# ---------------- Security headers
@app.after_request
def _secure(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    # If you later add CDNs/fonts, extend this CSP accordingly
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return resp

# ---------------- Pages
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# ---------------- Introspection
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET", "POST", "OPTIONS", "DELETE"}),
            "rule": str(rule),
        })
    return jsonify(sorted(table, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "model": ACTIVE_MODEL})

# ---------------- Models
@app.get("/api/models")
def list_models():
    return jsonify({"active": ACTIVE_MODEL, "available": AVAILABLE_MODELS})

@app.post("/api/model")
def set_model():
    global ACTIVE_MODEL
    data = request.get_json(silent=True) or {}
    name = str(data.get("model", "")).strip()
    if name not in AVAILABLE_MODELS:
        return jsonify({"error": "unknown_model", "available": AVAILABLE_MODELS}), 400
    ACTIVE_MODEL = name
    return jsonify({"ok": True, "active": ACTIVE_MODEL})

# ---------------- Stats
START_TS = int(time.time())

@app.get("/api/stats")
def stats():
    total_msgs = 0
    for cid in _all_cids():
        total_msgs += len(_load_thread(cid))
    return jsonify({
        "ok": True,
        "since_epoch": START_TS,
        "active_model": ACTIVE_MODEL,
        "num_clients": len(_all_cids()),
        "total_messages": total_msgs,
        "commit": COMMIT,
        "has_redis": bool(_redis),
        "rate_limit_enabled": bool(_limiter),
    })

# ---------------- Helpers
def _cid_from_request() -> str:
    # priority: explicit query → header → new guid
    cid = request.args.get("cid") or request.headers.get("X-Client-Id")
    return cid or (uuid.uuid4().hex)

def _dev_echo(user_msg: str) -> str:
    return f"(dev echo {COMMIT}) You said: {user_msg}"

def _openai_chat(user_msg: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
    if history:
        for m in history[-16:]:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_msg})
    resp = client.chat.completions.create(
        model=ACTIVE_MODEL,
        messages=messages,
        temperature=0.6,
    )
    return (resp.choices[0].message.content or "").strip()

# ---------------- Chat (POST) w/ history + rate limit
@app.post("/api/chat")
@limit("30/minute")
def api_chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "missing_message"}), 400

    cid = _cid_from_request()
    thread = _load_thread(cid)

    # add user
    thread.append({"role": "user", "content": user_msg, "ts": time.time()})

    # get assistant reply
    try:
        if not OPENAI_KEY:
            reply = _dev_echo(user_msg)
        else:
            reply = _openai_chat(user_msg, history=thread)
    except Exception as e:
        reply = f"(upstream error) {e!s}"

    # add assistant
    thread.append({"role": "assistant", "content": reply, "ts": time.time()})
    _save_thread(cid, thread)

    return jsonify({"reply": reply, "cid": cid})

# ---------------- Streaming (SSE)
@app.get("/api/chat/stream")
@limit("30/minute")
def chat_stream():
    # Accept ?q= OR JSON body
    q = request.args.get("q")
    if not q and request.data:
        try:
            q = (request.get_json(silent=True) or {}).get("message")
        except Exception:
            q = None
    user_msg = (q or "").strip()
    if not user_msg:
        return jsonify({"error": "missing_message"}), 400

    cid = _cid_from_request()
    thread = _load_thread(cid)
    thread.append({"role": "user", "content": user_msg, "ts": time.time()})
    _save_thread(cid, thread)

    def gen():
        def send(obj):
            yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        # Dev: simple fake streaming
        if not OPENAI_KEY:
            for chunk in ["(dev echo) ", "You said: ", user_msg]:
                time.sleep(0.03)
                yield from send({"delta": chunk})
            yield from send({"done": True})
            return

        # Real Streaming via OpenAI
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
        for m in thread[-16:]:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})

        stream = client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages,
            stream=True,
            temperature=0.6,
        )
        assembled = []
        for event in stream:
            delta = event.choices[0].delta.content or ""
            if delta:
                assembled.append(delta)
                yield from send({"delta": delta})
        reply = "".join(assembled).strip()
        thread.append({"role": "assistant", "content": reply, "ts": time.time()})
        _save_thread(cid, thread)
        yield from send({"done": True})

    return Response(gen(), mimetype="text/event-stream")

# ---------------- History
@app.get("/api/history")
def get_history():
    cid = _cid_from_request()
    msgs = _load_thread(cid)
    if not msgs:
        return jsonify({"error": "no_conversation"}), 404
    return jsonify({"messages": msgs, "cid": cid})

@app.get("/api/history/export")
def export_history():
    cid = _cid_from_request()
    msgs = _load_thread(cid)
    return jsonify({
        "cid": cid,
        "count": len(msgs),
        "model": ACTIVE_MODEL,
        "commit": COMMIT,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "messages": msgs,
    })

# NEW: Clear current cid’s history (used by “Clear Chat” in UI)
@app.delete("/api/history")
def clear_history():
    cid = _cid_from_request()
    _delete_thread(cid)
    return jsonify({"ok": True, "cid": cid})

# ---------------- Static passthrough
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------------- API-friendly errors
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









