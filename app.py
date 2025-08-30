# app.py
import os
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from collections import defaultdict, deque

# In-memory history per session (last 20 messages)
HISTORY: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))


# If your chat.html is under integrations/templates/chat.html keep this:
TEMPLATE_DIR = os.path.join("integrations", "templates")
STATIC_DIR = "static"

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", ""))
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")  # was gpt-4o-mini


# ----------------- UI PAGES -----------------
@app.get("/")
def home():
    # simple landing that uses the same template as /chat
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    # IMPORTANT: function name is different from the API function
    return render_template("chat.html", title="Friday AI")

# ----------------- OBSERVABILITY ------------
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

# ----------------- API ----------------------
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

    # Session id comes from header; fallback to 'anon'
    session_id = request.headers.get("X-Session-Id", "anon")
    session = HISTORY[session_id]

    # Record the user turn
    session.append({"role": "user", "content": user_msg, "ts": datetime.utcnow().isoformat() + "Z"})

    # If no OPENAI_API_KEY, reply with a friendly dev echo so the UI still works
    if not OPENAI_KEY:
        reply = f"Pong! How can I assist you today?\n\n(dev echo) You said: {user_msg}"
        session.append({"role": "assistant", "content": reply, "ts": datetime.utcnow().isoformat() + "Z"})
        return jsonify({"reply": reply}), 200

    # Real OpenAI call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", MODEL),
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                *[{"role": m["role"], "content": m["content"]} for m in list(session)],  # lite context
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        text = resp.choices[0].message.content.strip()
        session.append({"role": "assistant", "content": text, "ts": datetime.utcnow().isoformat() + "Z"})
        return jsonify({"reply": text}), 200
    except Exception as e:
        err = {"error": "upstream_error", "detail": str(e)}
        session.append({"role": "assistant", "content": json.dumps(err), "ts": datetime.utcnow().isoformat() + "Z"})
        return jsonify(err), 502


# -------- API: Model check
@app.get("/api/model")
def api_model():
    # Basic stats for quick sanity checks in prod
    sessions = len(HISTORY)
    # Use the header to scope stats to your current tab
    session_id = request.headers.get("X-Session-Id", "anon")
    sess = HISTORY.get(session_id, deque())
    return jsonify({
        "model": os.getenv("OPENAI_MODEL", MODEL),
        "commit": COMMIT,
        "sessions": sessions,
        "session_id": session_id,
        "messages_in_session": len(sess),
        "last_user": next((m["content"] for m in reversed(sess) if m["role"] == "user"), None),
        "last_reply": next((m["content"] for m in reversed(sess) if m["role"] == "assistant"), None),
    })




# ----------------- STATIC -------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.get("/api/history")
def api_history():
    session_id = request.args.get("session_id") or request.headers.get("X-Session-Id", "anon")
    turns = list(HISTORY.get(session_id, deque()))
    return jsonify({"session_id": session_id, "count": len(turns), "messages": turns})


# ----------------- ERROR PAGES --------------
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
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)

