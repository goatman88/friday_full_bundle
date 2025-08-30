# app.py
import os, json, time, uuid, base64
from datetime import datetime
from typing import List, Dict, Any, Optional
from functools import wraps

from flask import (
    Flask, jsonify, request, render_template, send_from_directory,
    Response, make_response
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

# Security/env
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")        # token for admin APIs
BASIC_USER   = os.getenv("BASIC_AUTH_USER", "")   # HTTP Basic user (for protected pages)
BASIC_PASS   = os.getenv("BASIC_AUTH_PASS", "")   # HTTP Basic pass (for protected pages)

# Optional: allow external CDNs/fonts in CSP. Comma-separated list of origins, e.g.:
# ASSET_CDN="https://fonts.googleapis.com,https://fonts.gstatic.com"
ASSET_CDN = [o.strip() for o in os.getenv("ASSET_CDN", "").split(",") if o.strip()]

# ---------------- Optional Redis persistence (falls back to memory)
_redis = None
try:
    from redis import Redis
    if os.getenv("REDIS_URL"):
        _redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
except Exception:
    _redis = None  # ok, fallback to memory

def _rkey(cid: str) -> str: return f"conv:{cid}"

def _load_thread(cid: str) -> List[Dict[str, Any]]:
    if _redis:
        raw = _redis.get(_rkey(cid))
        return json.loads(raw) if raw else []
    return _conversations.get(cid, [])

def _save_thread(cid: str, msgs: List[Dict[str, Any]]) -> None:
    if _redis: _redis.set(_rkey(cid), json.dumps(msgs))
    else: _conversations[cid] = msgs

def _delete_thread(cid: str) -> None:
    if _redis: _redis.delete(_rkey(cid))
    else: _conversations.pop(cid, None)

def _all_cids() -> List[str]:
    if _redis:
        cids: List[str] = []
        cursor = 0
        while True:
            cursor, keys = _redis.scan(cursor=cursor, match="conv:*", count=500)
            cids.extend([k.split(":", 1)[1] for k in keys])
            if cursor == 0: break
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

# ---------------- Basic Auth (for select pages & static when enabled)
def _basic_auth_enabled() -> bool:
    return bool(BASIC_USER and BASIC_PASS)

def _check_basic_auth(auth_header: str) -> bool:
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
        user, pwd = raw.split(":", 1)
        return (user == BASIC_USER) and (pwd == BASIC_PASS)
    except Exception:
        return False

def requires_basic_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _basic_auth_enabled():
            return fn(*args, **kwargs)  # gate OFF if creds not configured
        auth = request.headers.get("Authorization", "")
        if _check_basic_auth(auth):
            return fn(*args, **kwargs)
        resp = make_response("Unauthorized", 401)
        resp.headers["WWW-Authenticate"] = 'Basic realm="Friday Admin", charset="UTF-8"'
        return resp
    return wrapper

# ---------------- CSP / Security headers
def _csp_header() -> str:
    # Always allow self; optionally allow configured CDNs
    origins = "'self'"
    if ASSET_CDN:
        origins += " " + " ".join(ASSET_CDN)
    # Inline styles used by our templates → keep 'unsafe-inline' for style-src
    # Add data: for images & fonts; blob: for potential downloads/streams
    return (
        "default-src 'self'; "
        f"script-src {origins}; "
        f"style-src {origins} 'unsafe-inline'; "
        f"img-src {origins} data:; "
        f"font-src {origins} data:; "
        f"connect-src {origins}; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )

@app.after_request
def _secure(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = _csp_header()
    return resp

# ---------------- Pages
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# --- Admin Panel page (HTML UI) — protected by Basic Auth if configured
@app.get("/admin")
@requires_basic_auth
def admin_page():
    return render_template("admin.html", title="Friday Admin")

# ---------------- Introspection (protected by Basic Auth if configured)
@app.get("/routes")
@requires_basic_auth
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS","DELETE"}),
            "rule": str(rule),
        })
    return jsonify(sorted(table, key=lambda r: r["rule"]))

@app.get("/debug/health")
@requires_basic_auth
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
    total_msgs = sum(len(_load_thread(cid)) for cid in _all_cids())
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
    thread.append({"role": "user", "content": user_msg, "ts": time.time()})

    try:
        reply = _dev_echo(user_msg) if not OPENAI_KEY else _openai_chat(user_msg, history=thread)
    except Exception as e:
        reply = f"(upstream error) {e!s}"

    thread.append({"role": "assistant", "content": reply, "ts": time.time()})
    _save_thread(cid, thread)
    return jsonify({"reply": reply, "cid": cid})

# ---------------- Streaming (SSE via fetch)
@app.get("/api/chat/stream")
@limit("30/minute")
def chat_stream():
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
        def send(obj): yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        if not OPENAI_KEY:
            for chunk in ["(dev echo) ", "You said: ", user_msg]:
                time.sleep(0.03); yield from send({"delta": chunk})
            yield from send({"done": True}); return

        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
        for m in thread[-16:]:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})

        stream = client.chat.completions.create(model=ACTIVE_MODEL, messages=messages, stream=True, temperature=0.6)
        assembled = []
        for event in stream:
            delta = event.choices[0].delta.content or ""
            if delta:
                assembled.append(delta); yield from send({"delta": delta})
        reply = "".join(assembled).strip()
        thread.append({"role": "assistant", "content": reply, "ts": time.time()})
        _save_thread(cid, thread)
        yield from send({"done": True})

    return Response(gen(), mimetype="text/event-stream")

# ---------------- History (get/export/clear)
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

# downloadable file attachment (used by UI "Download")
@app.get("/api/history/export_file")
def export_history_file():
    cid = _cid_from_request()
    payload = {
        "cid": cid,
        "model": ACTIVE_MODEL,
        "commit": COMMIT,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "messages": _load_thread(cid),
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    resp = make_response(blob)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="friday_{cid[:8]}_{int(time.time())}.json"'
    return resp

@app.delete("/api/history")
def clear_history():
    cid = _cid_from_request()
    _delete_thread(cid)
    return jsonify({"ok": True, "cid": cid})

# ---------------- ADMIN (token-protected APIs)
def _require_admin() -> Optional[Response]:
    if not ADMIN_TOKEN:
        return make_response(jsonify({"error": "admin_disabled"}), 403)
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if tok != ADMIN_TOKEN:
        return make_response(jsonify({"error": "unauthorized"}), 401)
    return None

@app.get("/api/admin/cids")
def admin_cids():
    gate = _require_admin()
    if gate: return gate
    return jsonify({"ok": True, "cids": _all_cids(), "count": len(_all_cids())})

@app.delete("/api/admin/purge")
def admin_purge_one():
    gate = _require_admin()
    if gate: return gate
    cid = request.args.get("cid")
    if not cid:
        return jsonify({"error": "missing_cid"}), 400
    _delete_thread(cid)
    return jsonify({"ok": True, "purged": cid})

@app.delete("/api/admin/purge_all")
def admin_purge_all():
    gate = _require_admin()
    if gate: return gate
    purged = []
    for cid in _all_cids():
        _delete_thread(cid); purged.append(cid)
    return jsonify({"ok": True, "purged_count": len(purged), "purged": purged})

# ---------------- Static passthrough (protected by Basic Auth if configured)
@app.get("/static/<path:filename>")
@requires_basic_auth
def static_files(filename):
    resp = send_from_directory(app.static_folder, filename)
    # small perf win: cache immutable assets 1 hour (tune to your needs)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp

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












