# app.py
import os, json, time, uuid, base64, sqlite3, io, math, hashlib
from datetime import datetime, timedelta
from functools import wraps
from typing import List, Dict, Any, Optional, Tuple

from flask import (
    Flask, jsonify, request, render_template, send_from_directory,
    Response, make_response, send_file
)
from flask_cors import CORS

# ------------------------- App/Core -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")}})

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
BASIC_USER   = os.getenv("BASIC_AUTH_USER", "")
BASIC_PASS   = os.getenv("BASIC_AUTH_PASS", "")
JWT_SECRET   = os.getenv("JWT_SECRET", "change-me")
JWT_DAYS     = int(os.getenv("JWT_DAYS", "14"))
ENABLE_MOD   = os.getenv("ENABLE_MODERATION", "true").lower() in ("1","true","yes","on")
ASSET_CDN    = [o.strip() for o in os.getenv("ASSET_CDN", "").split(",") if o.strip()]
UPLOAD_DIR   = os.getenv("UPLOAD_DIR", "uploads"); os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_MB= int(os.getenv("MAX_UPLOAD_MB", "10"))

# Models
_default_models = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o3-mini"]
_env_models = [m.strip() for m in os.getenv("OPENAI_MODELS", "").split(",") if m.strip()]
AVAILABLE_MODELS = _env_models or _default_models
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", AVAILABLE_MODELS[0])
ACTIVE_MODEL  = DEFAULT_MODEL if DEFAULT_MODEL in AVAILABLE_MODELS else AVAILABLE_MODELS[0]

# Optional: Sentry
try:
    import sentry_sdk
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.05")))
except Exception:
    pass

# ------------------------- Storage (Redis → SQLite → Memory) -------------------------
_redis = None
try:
    from redis import Redis
    if os.getenv("REDIS_URL"):
        _redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
except Exception:
    _redis = None

DB_PATH = os.getenv("SQLITE_PATH", "friday.db")
_sqlite = None

def _sqlite_init():
    global _sqlite
    if _sqlite is not None: return
    _sqlite = sqlite3.connect(DB_PATH, check_same_thread=False)
    _sqlite.row_factory = sqlite3.Row
    # chat history
    _sqlite.execute("""CREATE TABLE IF NOT EXISTS messages (
        cid TEXT NOT NULL, user_id TEXT, role TEXT NOT NULL, content TEXT NOT NULL, ts REAL NOT NULL
    )""")
    _sqlite.execute("CREATE INDEX IF NOT EXISTS idx_messages_cid ON messages(cid)")
    _sqlite.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
    # users
    _sqlite.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, pwd_hash TEXT, created REAL
    )""")
    # docs (RAG)
    _sqlite.execute("""CREATE TABLE IF NOT EXISTS docs (
        id TEXT PRIMARY KEY, user_id TEXT, name TEXT, content TEXT, embedding TEXT, created REAL
    )""")
    _sqlite.commit()

def _use_sqlite(): return _redis is None

_conversations: Dict[str, List[Dict[str, Any]]] = {}

def _rkey(cid: str, user_id: Optional[str]) -> str:
    return f"conv:{user_id or 'anon'}:{cid}"

def _load_thread(cid: str, user_id: Optional[str]) -> List[Dict[str, Any]]:
    if _redis:
        raw = _redis.get(_rkey(cid, user_id))
        return json.loads(raw) if raw else []
    if _use_sqlite():
        _sqlite_init()
        cur = _sqlite.execute(
            "SELECT role, content, ts FROM messages WHERE cid = ? AND (user_id IS ? OR user_id = ?) ORDER BY ts ASC",
            (cid, user_id, user_id)
        )
        return [{"role": r["role"], "content": r["content"], "ts": r["ts"]} for r in cur.fetchall()]
    return _conversations.get((user_id or "anon")+":"+cid, [])

def _save_thread(cid: str, user_id: Optional[str], msgs: List[Dict[str, Any]]) -> None:
    if _redis:
        _redis.set(_rkey(cid, user_id), json.dumps(msgs)); return
    if _use_sqlite():
        _sqlite_init()
        with _sqlite:
            _sqlite.execute("DELETE FROM messages WHERE cid = ? AND (user_id IS ? OR user_id = ?)", (cid, user_id, user_id))
            _sqlite.executemany(
                "INSERT INTO messages (cid, user_id, role, content, ts) VALUES (?, ?, ?, ?, ?)",
                [(cid, user_id, m["role"], m["content"], float(m.get("ts", time.time()))) for m in msgs]
            )
        return
    _conversations[(user_id or "anon")+":"+cid] = msgs

def _delete_thread(cid: str, user_id: Optional[str]) -> None:
    if _redis: _redis.delete(_rkey(cid, user_id)); return
    if _use_sqlite():
        _sqlite_init()
        with _sqlite: _sqlite.execute("DELETE FROM messages WHERE cid = ? AND (user_id IS ? OR user_id = ?)", (cid, user_id, user_id))
        return
    _conversations.pop((user_id or "anon")+":"+cid, None)

def _all_cids() -> List[str]:
    if _redis:
        cids = []
        cursor = 0
        while True:
            cursor, keys = _redis.scan(cursor=cursor, match="conv:*", count=500)
            cids.extend([k.split(":")[-1] for k in keys])
            if cursor == 0: break
        return sorted(set(cids))
    if _use_sqlite():
        _sqlite_init()
        cur = _sqlite.execute("SELECT DISTINCT cid FROM messages ORDER BY cid ASC")
        return [r["cid"] for r in cur.fetchall()]
    # memory
    return sorted(set(k.split(":",1)[1] for k in _conversations.keys()))

def _purge_all() -> Tuple[int, List[str]]:
    if _redis:
        keys = _redis.keys("conv:*")
        cnt = len(keys)
        if cnt: _redis.delete(*keys)
        return cnt, [k.split(":")[-1] for k in keys]
    if _use_sqlite():
        _sqlite_init()
        cur = _sqlite.execute("SELECT DISTINCT cid FROM messages")
        cids = [r["cid"] for r in cur.fetchall()]
        with _sqlite: _sqlite.execute("DELETE FROM messages")
        return len(cids), cids
    cnt = len(_conversations); purged = list(_conversations.keys()); _conversations.clear()
    return cnt, purged

# ------------------------- Rate limit & usage -------------------------
_limiter = None
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _l = os.getenv("RATE_LIMIT", "60/minute")
    _limiter = Limiter(get_remote_address, app=app, default_limits=[_l])
except Exception:
    _limiter = None

def limit(rule: str):
    def deco(fn):
        return _limiter.limit(rule)(fn) if _limiter else fn
    return deco

def _approx_tokens(s: str) -> int:
    # very rough: ~4 chars/token
    return max(1, math.ceil(len(s)/4))

def _bump_usage(user_id: Optional[str], n_tokens: int):
    if not _redis: return
    key = f"usage:{user_id or 'anon'}:{time.strftime('%Y%m%d')}"
    _redis.incrby(key, n_tokens)
    _redis.expire(key, 2*24*3600)

@app.get("/api/usage")
def usage_today():
    if not _redis: return jsonify({"redis": False, "note": "attach REDIS_URL to enable usage counters"})
    user_id = (request.headers.get("X-User-Id") or "")
    key = f"usage:{user_id or 'anon'}:{time.strftime('%Y%m%d')}"
    val = int(_redis.get(key) or "0")
    return jsonify({"user_id": user_id or None, "tokens_est_today": val})

# ------------------------- Auth (JWT) -------------------------
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

def _jwt_issue(user_id: str) -> str:
    payload = {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()+JWT_DAYS*86400)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def _jwt_parse(token: str) -> Optional[str]:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data.get("sub")
    except Exception:
        return None

def auth_required(fn):
    @wraps(fn)
    def wrap(*a, **k):
        auth = request.headers.get("Authorization","")
        if auth.startswith("Bearer "):
            user_id = _jwt_parse(auth.split(" ",1)[1])
            if user_id:
                request.user_id = user_id
                return fn(*a, **k)
        return jsonify({"error":"auth_required"}), 401
    return wrap

def optional_auth(fn):
    @wraps(fn)
    def wrap(*a, **k):
        user_id = None
        auth = request.headers.get("Authorization","")
        if auth.startswith("Bearer "):
            user_id = _jwt_parse(auth.split(" ",1)[1])
        request.user_id = user_id
        return fn(*a, **k)
    return wrap

# users table helpers
def _user_get_by_email(email: str) -> Optional[sqlite3.Row]:
    _sqlite_init()
    cur = _sqlite.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cur.fetchone()

def _user_get(user_id: str) -> Optional[sqlite3.Row]:
    _sqlite_init()
    cur = _sqlite.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()

@app.post("/auth/register")
def auth_register():
    _sqlite_init()
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name  = (data.get("name") or "").strip()
    pwd   = (data.get("password") or "")
    if not (email and pwd): return jsonify({"error":"missing_fields"}), 400
    if _user_get_by_email(email): return jsonify({"error":"exists"}), 409
    uid = uuid.uuid4().hex
    with _sqlite:
        _sqlite.execute("INSERT INTO users (id,email,name,pwd_hash,created) VALUES (?,?,?,?,?)",
                        (uid, email, name, generate_password_hash(pwd), time.time()))
    return jsonify({"ok": True, "user_id": uid, "token": _jwt_issue(uid)})

@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    pwd   = (data.get("password") or "")
    row = _user_get_by_email(email)
    if not row or not check_password_hash(row["pwd_hash"], pwd):
        return jsonify({"error":"invalid_credentials"}), 401
    return jsonify({"ok": True, "user_id": row["id"], "token": _jwt_issue(row["id"]), "name": row["name"]})

@app.get("/auth/me")
@auth_required
def auth_me():
    row = _user_get(request.user_id)
    return jsonify({"user_id": row["id"], "email": row["email"], "name": row["name"]})

# ------------------------- Security helpers -------------------------
import base64 as _b64

def _basic_auth_enabled(): return bool(BASIC_USER and BASIC_PASS)
def _check_basic_auth(h: str) -> bool:
    if not h or not h.startswith("Basic "): return False
    try:
        raw = _b64.b64decode(h.split(" ",1)[1]).decode()
        u,p = raw.split(":",1); return u==BASIC_USER and p==BASIC_PASS
    except Exception: return False

def requires_basic_auth(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        if not _basic_auth_enabled(): return fn(*a, **k)
        if _check_basic_auth(request.headers.get("Authorization","")): return fn(*a, **k)
        resp = make_response("Unauthorized", 401)
        resp.headers["WWW-Authenticate"] = 'Basic realm="Friday Admin", charset="UTF-8"'
        return resp
    return wrapper

def _csp_header() -> str:
    origins = "'self'"
    if ASSET_CDN: origins += " " + " ".join(ASSET_CDN)
    return (
        "default-src 'self'; "
        f"script-src {origins}; style-src {origins} 'unsafe-inline'; "
        f"img-src {origins} data:; font-src {origins} data:; connect-src {origins}; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )

@app.after_request
def _secure(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = _csp_header()
    return resp

# ------------------------- Logging -------------------------
@app.before_request
def _json_log():
    if request.path.startswith("/api/"):
        try:
            print(json.dumps({
                "ts": int(time.time()),
                "path": request.path,
                "method": request.method,
                "ip": request.headers.get("X-Forwarded-For") or request.remote_addr,
                "cid": request.args.get("cid") or request.headers.get("X-Client-Id"),
                "user": getattr(request, "user_id", None)
            }))
        except Exception:
            pass

# ------------------------- Pages -------------------------
@app.get("/")
def home(): return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page(): return render_template("chat.html", title="Friday AI")

@app.get("/admin")
@requires_basic_auth
def admin_page(): return render_template("admin.html", title="Friday Admin")

@app.get("/login")
def login_page(): return render_template("login.html", title="Login • Friday")

# ------------------------- Introspection -------------------------
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
    store = "redis" if _redis else ("sqlite" if _use_sqlite() else "memory")
    return jsonify({"ok": True, "commit": COMMIT, "model": ACTIVE_MODEL, "store": store, "db_path": DB_PATH if _use_sqlite() else None})

# ------------------------- Utilities -------------------------
@app.get("/api/ping")
def ping(): return jsonify({"pong": True, "commit": COMMIT, "now": int(time.time())})

@app.get("/api/info")
def info():
    return jsonify({
        "commit": COMMIT, "has_openai_key": bool(OPENAI_KEY),
        "active_model": ACTIVE_MODEL, "available_models": AVAILABLE_MODELS,
        "upload_dir": os.path.abspath(UPLOAD_DIR), "max_upload_mb": MAX_UPLOAD_MB
    })

# ------------------------- Model switch -------------------------
@app.get("/api/models")
def list_models(): return jsonify({"active": ACTIVE_MODEL, "available": AVAILABLE_MODELS})

@app.post("/api/model")
def set_model():
    global ACTIVE_MODEL
    name = (request.get_json(silent=True) or {}).get("model")
    if not name or name not in AVAILABLE_MODELS:
        return jsonify({"error":"unknown_model","available":AVAILABLE_MODELS}), 400
    ACTIVE_MODEL = name
    return jsonify({"ok": True, "active": ACTIVE_MODEL})

# ------------------------- OpenAI helpers -------------------------
def _openai_chat(user_msg: str, history: Optional[List[Dict[str,str]]] = None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    messages = [{"role":"system","content":"You are Friday AI. Be brief, friendly, and helpful."}]
    if history:
        for m in history[-16:]:
            if m["role"] in ("user","assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role":"user","content":user_msg})
    resp = client.chat.completions.create(model=ACTIVE_MODEL, messages=messages, temperature=0.6)
    return (resp.choices[0].message.content or "").strip()

def _openai_embed(texts: List[str]) -> List[List[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    model = os.getenv("EMBED_MODEL","text-embedding-3-small")
    r = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in r.data]

def _openai_moderate(text: str) -> Dict[str,Any]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    r = client.moderations.create(model="omni-moderation-latest", input=text)
    res = r.results[0]
    return {"flagged": bool(res.flagged), "categories": res.categories}

# ------------------------- Chat + Stream (with guardrails) -------------------------
def _cid_from_request() -> str:
    return (request.args.get("cid") or request.headers.get("X-Client-Id") or uuid.uuid4().hex)

def _dev_echo(msg: str) -> str:
    return f"(dev echo {COMMIT}) You said: {msg}"

@app.post("/api/chat")
@optional_auth
@limit("30/minute")
def api_chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg: return jsonify({"error":"missing_message"}), 400
    cid = _cid_from_request(); user_id = request.user_id

    # Guardrails
    if ENABLE_MOD and OPENAI_KEY:
        try:
            m = _openai_moderate(user_msg)
            if m.get("flagged"):
                return jsonify({"error":"moderation_flagged","detail":m}), 400
        except Exception:
            pass

    thread = _load_thread(cid, user_id)
    thread.append({"role":"user","content":user_msg,"ts":time.time()})

    try:
        reply = _dev_echo(user_msg) if not OPENAI_KEY else _openai_chat(user_msg, history=thread)
    except Exception as e:
        reply = f"(upstream error) {e!s}"

    thread.append({"role":"assistant","content":reply,"ts":time.time()})
    _save_thread(cid, user_id, thread)
    _bump_usage(user_id, _approx_tokens(user_msg) + _approx_tokens(reply))
    return jsonify({"reply": reply, "cid": cid})

@app.get("/api/chat/stream")
@optional_auth
@limit("30/minute")
def chat_stream():
    q = request.args.get("q")
    if not q and request.data:
        try: q = (request.get_json(silent=True) or {}).get("message")
        except Exception: q = None
    user_msg = (q or "").strip()
    if not user_msg: return jsonify({"error":"missing_message"}), 400
    cid = _cid_from_request(); user_id = request.user_id

    # Guardrails
    if ENABLE_MOD and OPENAI_KEY:
        try:
            m = _openai_moderate(user_msg)
            if m.get("flagged"): return jsonify({"error":"moderation_flagged","detail":m}), 400
        except Exception:
            pass

    thread = _load_thread(cid, user_id)
    thread.append({"role":"user","content":user_msg,"ts":time.time()})
    _save_thread(cid, user_id, thread)

    def gen():
        def send(obj): yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        if not OPENAI_KEY:
            acc = ""
            for chunk in ["(dev echo) ","You said: ", user_msg]:
                time.sleep(0.03); acc += chunk; yield from send({"delta": chunk})
            _bump_usage(user_id, _approx_tokens(user_msg)+_approx_tokens(acc))
            yield from send({"done": True}); return

        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        messages = [{"role":"system","content":"You are Friday AI. Be brief, friendly, and helpful."}]
        for m in thread[-16:]:
            if m["role"] in ("user","assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role":"user","content":user_msg})
        stream = client.chat.completions.create(model=ACTIVE_MODEL, messages=messages, stream=True, temperature=0.6)
        assembled = []
        for event in stream:
            delta = event.choices[0].delta.content or ""
            if delta:
                assembled.append(delta); yield from send({"delta": delta})
        reply = "".join(assembled).strip()
        thread.append({"role":"assistant","content":reply,"ts":time.time()})
        _save_thread(cid, user_id, thread)
        _bump_usage(user_id, _approx_tokens(user_msg)+_approx_tokens(reply))
        yield from send({"done": True})

    return Response(gen(), mimetype="text/event-stream")

# ------------------------- Moderation API -------------------------
@app.post("/api/moderate")
def moderate():
    text = (request.get_json(silent=True) or {}).get("text","")
    if not text: return jsonify({"error":"missing_text"}), 400
    if not OPENAI_KEY: return jsonify({"flagged": False, "categories": {}, "dev": True})
    try:
        return jsonify(_openai_moderate(text))
    except Exception as e:
        return jsonify({"error":"upstream_error","detail":str(e)}), 502

# ------------------------- Text-to-Image -------------------------
@app.post("/api/image")
def image_generate():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    size = (data.get("size") or "1024x1024").strip()
    if not prompt: return jsonify({"error":"missing_prompt"}), 400
    if not OPENAI_KEY:
        return jsonify({"error":"image_gen_disabled","detail":"No OPENAI_API_KEY set"}), 501
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        img = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
        b64 = img.data[0].b64_json
        raw = base64.b64decode(b64)
        return send_file(io.BytesIO(raw), mimetype="image/png", download_name="image.png")
    except Exception as e:
        return jsonify({"error":"upstream_error","detail":str(e)}), 502

# ------------------------- Files (upload/list/delete) -------------------------
@app.post("/api/files")
def files_upload():
    if "file" not in request.files: return jsonify({"error":"missing_file"}), 400
    f = request.files["file"]
    if not f.filename: return jsonify({"error":"empty_filename"}), 400
    f.stream.seek(0,2); size = f.stream.tell(); f.stream.seek(0)
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        return jsonify({"error":"file_too_large","max_mb":MAX_UPLOAD_MB}), 413
    ext = os.path.splitext(f.filename)[1]
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    f.save(path)
    return jsonify({"ok": True, "filename": name, "size": size})

@app.get("/api/files")
def files_list():
    files = []
    for fn in sorted(os.listdir(UPLOAD_DIR)):
        p = os.path.join(UPLOAD_DIR, fn)
        if os.path.isfile(p):
            files.append({"name": fn, "size": os.path.getsize(p)})
    return jsonify({"files": files})

@app.delete("/api/files")
def files_delete():
    name = request.args.get("name")
    if not name: return jsonify({"error":"missing_name"}), 400
    p = os.path.join(UPLOAD_DIR, name)
    if not os.path.isfile(p): return jsonify({"error":"not_found"}), 404
    os.remove(p)
    return jsonify({"ok": True, "deleted": name})

@app.get("/static/<path:filename>")
@requires_basic_auth
def static_files(filename):
    resp = send_from_directory(app.static_folder, filename)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp

# ------------------------- History (per-user) -------------------------
@app.get("/api/history")
@optional_auth
def get_history():
    cid = _cid_from_request()
    msgs = _load_thread(cid, request.user_id)
    if not msgs: return jsonify({"error":"no_conversation"}), 404
    return jsonify({"messages": msgs, "cid": cid})

@app.get("/api/history/export")
@optional_auth
def export_history():
    cid = _cid_from_request()
    msgs = _load_thread(cid, request.user_id)
    return jsonify({"cid": cid, "count": len(msgs), "model": ACTIVE_MODEL,
                    "commit": COMMIT, "exported_at": datetime.utcnow().isoformat()+"Z", "messages": msgs})

@app.get("/api/history/export_file")
@optional_auth
def export_history_file():
    cid = _cid_from_request()
    payload = {"cid": cid, "model": ACTIVE_MODEL, "commit": COMMIT,
               "exported_at": datetime.utcnow().isoformat()+"Z", "messages": _load_thread(cid, request.user_id)}
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    resp = make_response(blob)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="friday_{cid[:8]}_{int(time.time())}.json"'
    return resp

@app.post("/api/history/import")
@optional_auth
def import_history():
    cid = _cid_from_request()
    msgs = (request.get_json(silent=True) or {}).get("messages")
    if not isinstance(msgs, list): return jsonify({"error":"invalid_payload","detail":"messages must be a list"}), 400
    if len(msgs) > 2000: return jsonify({"error":"too_many_messages"}), 413
    cleaned = []
    for m in msgs:
        role = (m.get("role") or "").strip()
        if role not in ("user","assistant","system"): continue
        content = str(m.get("content","")); ts = float(m.get("ts", time.time()))
        cleaned.append({"role": role, "content": content, "ts": ts})
    _save_thread(cid, request.user_id, cleaned)
    return jsonify({"ok": True, "cid": cid, "count": len(cleaned)})

@app.delete("/api/history")
@optional_auth
def clear_history():
    cid = _cid_from_request()
    _delete_thread(cid, request.user_id)
    return jsonify({"ok": True, "cid": cid})

# ------------------------- Admin (backup/restore) -------------------------
def _require_admin():
    if not ADMIN_TOKEN: return make_response(jsonify({"error":"admin_disabled"}), 403)
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if tok != ADMIN_TOKEN: return make_response(jsonify({"error":"unauthorized"}), 401)
    return None

@app.get("/api/admin/cids")
def admin_cids():
    gate = _require_admin()
    if gate: return gate
    cids = _all_cids()
    return jsonify({"ok": True, "cids": cids, "count": len(cids)})

@app.delete("/api/admin/purge")
def admin_purge_one():
    gate = _require_admin()
    if gate: return gate
    cid = request.args.get("cid")
    if not cid: return jsonify({"error":"missing_cid"}), 400
    # purge for all users who used this cid
    if _use_sqlite():
        _sqlite_init()
        with _sqlite: _sqlite.execute("DELETE FROM messages WHERE cid = ?", (cid,))
    else:
        # redis/memory: blunt instrument
        for u in (None, "anon"):
            _delete_thread(cid, None)
    return jsonify({"ok": True, "purged": cid})

@app.delete("/api/admin/purge_all")
def admin_purge_all():
    gate = _require_admin()
    if gate: return gate
    count, purged = _purge_all()
    return jsonify({"ok": True, "purged_count": count, "purged": purged})

@app.get("/api/admin/backup")
def admin_backup():
    gate = _require_admin()
    if gate: return gate
    out = {}
    if _use_sqlite():
        _sqlite_init()
        cur = _sqlite.execute("SELECT DISTINCT cid FROM messages")
        for r in cur.fetchall():
            cid = r["cid"]; out[cid] = _load_thread(cid, None)  # anonymous superset
    else:
        for cid in _all_cids(): out[cid] = _load_thread(cid, None)
    return jsonify({
        "ok": True, "generated_at": datetime.utcnow().isoformat()+"Z",
        "model": ACTIVE_MODEL, "commit": COMMIT,
        "sessions": out, "count": len(out),
        "messages_total": sum(len(v) for v in out.values()),
    })

@app.get("/api/admin/backup_file")
def admin_backup_file():
    gate = _require_admin()
    if gate: return gate
    payload = (admin_backup().json if hasattr(admin_backup(), "json") else None)
    if payload is None:
        out = {cid: _load_thread(cid, None) for cid in _all_cids()}
        payload = {"ok": True, "generated_at": datetime.utcnow().isoformat()+"Z",
                   "model": ACTIVE_MODEL, "commit": COMMIT, "sessions": out}
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    resp = make_response(blob)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="friday_backup_{int(time.time())}.json"'
    return resp

@app.post("/api/admin/restore")
def admin_restore():
    gate = _require_admin()
    if gate: return gate
    data = request.get_json(silent=True) or {}
    sessions = data.get("sessions"); merge = bool(data.get("merge", False))
    if not isinstance(sessions, dict):
        return jsonify({"error":"invalid_payload","detail":"sessions must be an object"}), 400
    if not merge: _purge_all()
    written_sessions = 0; written_msgs = 0
    for cid, msgs in sessions.items():
        cleaned = []
        for m in msgs:
            role = (m.get("role") or "").strip()
            if role not in ("user","assistant","system"): continue
            content = str(m.get("content","")); ts = float(m.get("ts", time.time()))
            cleaned.append({"role": role, "content": content, "ts": ts})
        _save_thread(cid, None, cleaned)
        written_sessions += 1; written_msgs += len(cleaned)
    return jsonify({"ok": True, "merge": merge,
                    "sessions_written": written_sessions, "messages_written": written_msgs})

# ------------------------- RAG: ingest + search -------------------------
def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a)!=len(b): return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    if na==0 or nb==0: return 0.0
    return dot/(na*nb)

@app.post("/api/rag/ingest")
@auth_required
def rag_ingest():
    if not OPENAI_KEY:
        return jsonify({"error":"no_openai_key"}), 501
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or f"doc-{uuid.uuid4().hex[:8]}").strip()
    content = (data.get("text") or "").strip()
    if not content: return jsonify({"error":"missing_text"}), 400
    vec = _openai_embed([content])[0]
    _sqlite_init()
    with _sqlite:
        _sqlite.execute("INSERT INTO docs (id,user_id,name,content,embedding,created) VALUES (?,?,?,?,?,?)",
                        (uuid.uuid4().hex, request.user_id, name, content, json.dumps(vec), time.time()))
    return jsonify({"ok": True, "name": name, "tokens_est": _approx_tokens(content)})

@app.get("/api/rag/search")
@auth_required
def rag_search():
    q = (request.args.get("q") or "").strip()
    k = int(request.args.get("k","3"))
    if not q: return jsonify({"error":"missing_q"}), 400
    qv = _openai_embed([q])[0] if OPENAI_KEY else []
    _sqlite_init()
    cur = _sqlite.execute("SELECT id,name,content,embedding,created FROM docs WHERE user_id = ? ORDER BY created DESC LIMIT 500", (request.user_id,))
    rows = cur.fetchall()
    scored = []
    for r in rows:
        try:
            v = json.loads(r["embedding"])
            score = _cosine(qv, v) if qv else 0.0
            scored.append({"id": r["id"], "name": r["name"], "snippet": r["content"][:300], "score": round(score,4)})
        except Exception:
            continue
    scored.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"q": q, "k": k, "results": scored[:k]})

# ------------------------- Tools: Weather (no key) -------------------------
@app.get("/api/tools/weather")
def tool_weather():
    import requests
    city = (request.args.get("q") or "").strip()
    if not city: return jsonify({"error":"missing_q"}), 400
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language":"en"}).json()
        if not g.get("results"): return jsonify({"error":"not_found"}), 404
        lat = g["results"][0]["latitude"]; lon = g["results"][0]["longitude"]
        f = requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude":lat,"longitude":lon,"hourly":"temperature_2m","current_weather":True}).json()
        return jsonify({"city": g["results"][0]["name"], "lat":lat, "lon":lon, "current": f.get("current_weather")})
    except Exception as e:
        return jsonify({"error":"upstream_error","detail":str(e)}), 502

# ------------------------- Errors -------------------------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error":"not_found","path":request.path}), 404
    return "Not Found", 404

@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify({"error":"method_not_allowed","path":request.path}), 405
    return "Method Not Allowed", 405

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
















