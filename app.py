# app.py
import os, json, time, uuid, sqlite3
from datetime import datetime, timezone
from contextlib import closing
from functools import wraps

from flask import (
    Flask, jsonify, request, render_template, send_from_directory,
    session, redirect, url_for, Response, abort
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ---------- App setup
ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data.sqlite")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-please-change")
CORS(app, supports_credentials=True)

limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")

COMMIT = os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LOGIN_PASSWORD = os.getenv("SECRET_PASSWORD", "")  # optional; if empty, auth is disabled

# ---------- DB bootstrap
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(db()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations(
              id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS messages(
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );
            CREATE TABLE IF NOT EXISTS events(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              at TEXT NOT NULL,
              meta TEXT
            );
            """
        )

init_db()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def track(name, **meta):
    try:
        with closing(db()) as conn, conn:
            conn.execute(
                "INSERT INTO events(id,name,at,meta) VALUES(?,?,?,?)",
                (str(uuid.uuid4()), name, now_iso(), json.dumps(meta)),
            )
    except Exception:
        pass

# ---------- Auth helpers
def is_authed():
    if not LOGIN_PASSWORD:
        return True  # auth disabled
    return session.get("authed") is True

def require_auth(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if is_authed():
            return view(*a, **kw)
        return redirect(url_for("login", next=request.path))
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if not LOGIN_PASSWORD:
        return redirect(url_for("chat_page"))
    err = None
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == LOGIN_PASSWORD:
            session["authed"] = True
            track("login_ok", ip=get_remote_address())
            return redirect(request.args.get("next") or url_for("chat_page"))
        err = "Incorrect password."
        track("login_fail", ip=get_remote_address())
    return render_template("login.html", title="Sign in", error=err)

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- Pages
@app.get("/")
def home():
    return redirect(url_for("chat_page"))

@app.get("/chat")
@require_auth
def chat_page():
    # create or fetch a session conversation
    if "conversation_id" not in session:
        cid = str(uuid.uuid4())
        session["conversation_id"] = cid
        with closing(db()) as conn, conn:
            conn.execute(
                "INSERT INTO conversations(id,created_at,user_id) VALUES(?,?,?)",
                (cid, now_iso(), None),
            )
    return render_template("chat.html", title="Friday AI")

# ---------- Observability
@app.get("/routes")
def routes():
    table = []
    for r in app.url_map.iter_rules():
        table.append({
            "endpoint": r.endpoint,
            "methods": sorted(m for m in r.methods if m in {"GET","POST","OPTIONS"}),
            "rule": str(r),
        })
    return jsonify(sorted(table, key=lambda x: x["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT})

@app.get("/api/model")
def get_model():
    return jsonify({"model": MODEL, "has_key": bool(OPENAI_KEY)})

# ---------- History (DB-backed)
@app.get("/api/history")
def get_history():
    cid = session.get("conversation_id")
    if not cid:
        return jsonify([])
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
            (cid,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.delete("/api/history")
def clear_history():
    cid = session.get("conversation_id")
    if not cid:
        return jsonify({"ok": True})
    with closing(db()) as conn, conn:
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    track("history_cleared")
    return jsonify({"ok": True})

def store_msg(cid, role, content):
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
            (str(uuid.uuid4()), cid, role, content, now_iso()),
        )

# ---------- Chat (non-stream)
@app.post("/api/chat")
@limiter.limit("15/minute")
def api_chat():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400
    user_msg = str(data.get("message", "")).strip() or "Hello!"
    cid = session.get("conversation_id") or str(uuid.uuid4())
    session["conversation_id"] = cid

    store_msg(cid, "user", user_msg)
    track("chat_hit", stream=False)

    # Dev echo (no key)
    if not OPENAI_KEY:
        reply = f"Hello there! 😊\n\n(dev echo) You said: {user_msg}"
        store_msg(cid, "assistant", reply)
        return jsonify({"reply": reply})

    # Real OpenAI call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", MODEL),
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                *[{"role": r["role"], "content": r["content"]} for r in json.loads(get_history().data or "[]")],
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        text = resp.choices[0].message.content.strip()
        store_msg(cid, "assistant", text)
        return jsonify({"reply": text})
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        track("openai_error", detail=err)
        return jsonify({"error": "upstream_error", "detail": err}), 502

# ---------- Chat (streaming: text/event-stream)
@app.post("/api/chat_stream")
@limiter.limit("20/minute")
def api_chat_stream():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error":"Invalid JSON"}), 400
    user_msg = str(data.get("message","")).strip() or "Hello!"
    cid = session.get("conversation_id") or str(uuid.uuid4())
    session["conversation_id"] = cid

    store_msg(cid, "user", user_msg)
    track("chat_hit", stream=True)

    def sse(data_obj):
        return f"data: {json.dumps(data_obj, ensure_ascii=False)}\n\n"

    def generate():
        # typing indicator start
        yield sse({"type":"start"})
        if not OPENAI_KEY:
            # fake stream
            chunks = ["Hello", " there!", " (dev echo): ", user_msg]
            acc = ""
            for c in chunks:
                time.sleep(0.05)
                acc += c
                yield sse({"type":"delta","text":c})
            store_msg(cid, "assistant", acc)
            yield sse({"type":"done"})
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            stream = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", MODEL),
                messages=[
                    {"role":"system","content":"You are Friday AI. Be brief, friendly, and helpful."},
                    *[{"role": r["role"], "content": r["content"]} for r in json.loads(get_history().data or "[]")],
                    {"role":"user","content":user_msg},
                ],
                stream=True,
                temperature=0.6,
            )
            acc = ""
            for evt in stream:
                delta = getattr(getattr(evt, "choices", [{}])[0], "delta", None)
                text = getattr(delta, "content", None) if delta else None
                if text:
                    acc += text
                    yield sse({"type":"delta","text":text})
            store_msg(cid, "assistant", acc.strip())
            yield sse({"type":"done"})
        except Exception as e:
            yield sse({"type":"error","detail":str(e)})

    return Response(generate(), mimetype="text/event-stream")

# ---------- Analytics (very simple)
@app.get("/debug/stats")
def stats():
    with closing(db()) as conn:
        msg_count = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        convos     = conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
        last_event = conn.execute("SELECT name,at FROM events ORDER BY at DESC LIMIT 1").fetchone()
    return jsonify({
        "messages": msg_count,
        "conversations": convos,
        "last_event": dict(last_event) if last_event else None,
        "model": MODEL, "has_key": bool(OPENAI_KEY), "commit": COMMIT
    })

# ---------- Static passthrough
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- API error pages
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



