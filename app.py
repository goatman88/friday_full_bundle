# app.py
import os
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

# If your chat.html is under integrations/templates/chat.html keep this:
TEMPLATE_DIR = os.path.join("integrations", "templates")
STATIC_DIR = "static"

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", ""))
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
    """
    Request JSON:
      { "message": "Hi", "history": [ {"role":"user","content":"..."},
                                      {"role":"assistant","content":"..."},
                                      ... ] }   # optional
    """
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    user_msg = str(data.get("message", "")).strip() or "Hello!"
    raw_history = data.get("history") or []

    # Normalize & cap history (last 12 messages, user/assistant only)
    history: list[dict] = []
    for m in raw_history[-12:]:
        if not isinstance(m, dict):
            continue
        role = (m.get("role") or "").lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(m.get("content") or "").strip()
        if content:
            history.append({"role": role, "content": content})

    # Dev echo if running without a key
    if not OPENAI_KEY:
        reply = f"(dev echo) You said: {user_msg}"
        if history:
            reply = f"(dev echo w/ history {len(history)} msgs) You said: {user_msg}"
        return jsonify({"reply": reply}), 200

    # Real OpenAI call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        messages = [{"role": "system",
                     "content": "You are Friday AI. Be brief, friendly, and helpful."}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", MODEL),
            messages=messages,
            temperature=0.6,
            max_tokens=400,
        )
        text = (resp.choices[0].message.content or "").strip()
        return jsonify({"reply": text}), 200
    except Exception as e:
        return jsonify({"error": "upstream_error", "detail": str(e)}), 502


# ----------------- STATIC -------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

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

