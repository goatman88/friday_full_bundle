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
def chat_api():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({"error": "Invalid request: expected JSON with 'message'"}), 400

    user_msg = (data.get("message") or "").strip() or "Hello!"

    # Dev echo if no key is set (keeps UI usable)
    if not OPENAI_KEY:
        return jsonify({"reply": f"Hi there!\n\n(dev echo) You said: {user_msg}"}), 200

    # Real OpenAI call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be brief, friendly, and helpful."},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        text = resp.choices[0].message.content.strip()
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

