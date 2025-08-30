# app.py
import os
import json
import time
import threading
from datetime import datetime
from collections import deque, OrderedDict
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

# ------------------------------------------------------------------------------------
# Flask setup
# ------------------------------------------------------------------------------------
# NOTE: Change template_folder to "integrations/templates" if that's where chat.html is.
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", ""))
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")  # default; env var overrides

# ------------------------------------------------------------------------------------
# History store (LRU + optional Redis persistence, TTL)
# ------------------------------------------------------------------------------------
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "200"))            # cap total sessions in memory
HISTORY_TTL  = int(os.getenv("HISTORY_TTL_SECONDS", "0"))       # 0 = no TTL; else seconds
PER_SESSION_MAXLEN = int(os.getenv("PER_SESSION_MAXLEN", "20")) # messages kept per session
REDIS_URL = os.getenv("REDIS_URL")                              # optional Redis (Upstash, etc.)
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "friday:history:")

_redis = None
if REDIS_URL:
    try:
        import redis
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        _redis = None  # fallback to file

_TMP_FILE = "/tmp/friday_history.jsonl"

def _persist_file(session_id: str, messages: list[dict]):
    try:
        with open(_TMP_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "session_id": session_id, "messages": messages}) + "\n")
    except Exception:
        pass

def _load_file_latest(session_id: str) -> list[dict]:
    try:
        last = None
        with open(_TMP_FILE, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                if obj.get("session_id") == session_id:
                    last = obj.get("messages")
        return last or []
    except Exception:
        return []

class HistoryStore:
    def __init__(self, max_sessions=200, per_session_maxlen=20, ttl_seconds=0):
        self.max_sessions = max_sessions
        self.per_session_maxlen = per_session_maxlen
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._lru: OrderedDict[str, deque] = OrderedDict()
        self._last_seen: dict[str, float] = {}

    def _touch(self, sid: str):
        now = time.time()
        self._last_seen[sid] = now
        if sid in self._lru:
            self._lru.move_to_end(sid)

    def _maybe_evict(self):
        # TTL eviction
        if self.ttl > 0:
            cutoff = time.time() - self.ttl
            for sid in list(self._lru.keys()):
                if self._last_seen.get(sid, 0) < cutoff:
                    self._lru.pop(sid, None)
                    self._last_seen.pop(sid, None)
        # LRU size eviction
        while len(self._lru) > self.max_sessions:
            sid, _ = self._lru.popitem(last=False)
            self._last_seen.pop(sid, None)

    def _load_from_persistence(self, sid: str) -> list[dict]:
        # Redis first
        if _redis:
            try:
                raw = _redis.get(REDIS_PREFIX + sid)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        # file fallback
        return _load_file_latest(sid)

    def _save_to_persistence(self, sid: str, messages: list[dict]):
        # Redis first
        if _redis:
            try:
                raw = json.dumps(messages)
                if self.ttl > 0:
                    _redis.setex(REDIS_PREFIX + sid, self.ttl, raw)
                else:
                    _redis.set(REDIS_PREFIX + sid, raw)
                return
            except Exception:
                pass
        # file fallback
        _persist_file(sid, messages)

    def get_session(self, sid: str) -> deque:
        with self._lock:
            if sid not in self._lru:
                # create from persistence if any
                messages = self._load_from_persistence(sid)
                dq = deque(messages, maxlen=self.per_session_maxlen)
                self._lru[sid] = dq
            self._touch(sid)
            self._maybe_evict()
            return self._lru[sid]

    def append(self, sid: str, role: str, content: str):
        with self._lock:
            dq = self.get_session(sid)
            dq.append({"role": role, "content": content, "ts": datetime.utcnow().isoformat() + "Z"})
            self._save_to_persistence(sid, list(dq))
            self._touch(sid)
            self._maybe_evict()

    def get_messages(self, sid: str) -> list[dict]:
        with self._lock:
            dq = self.get_session(sid)
            return list(dq)

    def stats(self) -> dict:
        with self._lock:
            return {
                "sessions": len(self._lru),
                "max_sessions": self.max_sessions,
                "ttl_seconds": self.ttl,
                "using_redis": bool(_redis),
            }

STORE = HistoryStore(max_sessions=MAX_SESSIONS, per_session_maxlen=PER_SESSION_MAXLEN, ttl_seconds=HISTORY_TTL)

# ------------------------------------------------------------------------------------
# OpenAI client (SDK v1.x) — lazy init, works with env var
# ------------------------------------------------------------------------------------
_openai_client = None
def get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        if OPENAI_KEY:
            _openai_client = OpenAI(api_key=OPENAI_KEY)
        else:
            _openai_client = OpenAI()  # uses env OPENAI_API_KEY
    return _openai_client

# ------------------------------------------------------------------------------------
# UI pages
# ------------------------------------------------------------------------------------
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")

# ------------------------------------------------------------------------------------
# Observability / utils
# ------------------------------------------------------------------------------------
@app.get("/routes")
def routes():
    rows = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m in {"GET", "POST", "OPTIONS"})
        rows.append({"endpoint": rule.endpoint, "methods": methods, "rule": str(rule)})
    rows.sort(key=lambda r: r["rule"])
    return jsonify(rows)

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT})

# ------------------------------------------------------------------------------------
# API: chat
# ------------------------------------------------------------------------------------
@app.post("/api/chat")
def api_chat():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    user_msg = (str(data.get("message", "")).strip() or "Hello!")
    session_id = request.headers.get("X-Session-Id", "anon")

    # record user turn
    STORE.append(session_id, "user", user_msg)

    # no key? dev echo
    if not OPENAI_KEY and not os.getenv("OPENAI_API_KEY"):
        reply = f"(dev echo) You said: {user_msg}"
        STORE.append(session_id, "assistant", reply)
        return jsonify({"reply": reply}), 200

    # real call
    try:
        client = get_openai()
        history = STORE.get_messages(session_id)
        messages = [{"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history]
        messages += [{"role": "user", "content": user_msg}]

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", MODEL),
            messages=messages,
            temperature=0.6,
        )
        text = (resp.choices[0].message.content or "").strip()
        STORE.append(session_id, "assistant", text)
        return jsonify({"reply": text}), 200
    except Exception as e:
        err = {"error": "upstream_error", "detail": str(e)}
        STORE.append(session_id, "assistant", json.dumps(err))
        return jsonify(err), 502

# ------------------------------------------------------------------------------------
# API: model info + session counters
# ------------------------------------------------------------------------------------
@app.get("/api/model")
def api_model():
    stats = STORE.stats()
    session_id = request.headers.get("X-Session-Id", "anon")
    msgs = STORE.get_messages(session_id)
    return jsonify({
        "model": os.getenv("OPENAI_MODEL", MODEL),
        "commit": COMMIT,
        **stats,
        "session_id": session_id,
        "messages_in_session": len(msgs),
        "last_user": next((m["content"] for m in reversed(msgs) if m["role"] == "user"), None),
        "last_reply": next((m["content"] for m in reversed(msgs) if m["role"] == "assistant"), None),
    })

# ------------------------------------------------------------------------------------
# API: history inspector
# ------------------------------------------------------------------------------------
@app.get("/api/history")
def api_history():
    session_id = request.args.get("session_id") or request.headers.get("X-Session-Id", "anon")
    messages = STORE.get_messages(session_id)
    return jsonify({"session_id": session_id, "count": len(messages), "messages": messages})

# ------------------------------------------------------------------------------------
# Static passthrough + friendly errors
# ------------------------------------------------------------------------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

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

# ------------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)

