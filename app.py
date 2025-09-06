import os
import io
import logging
from datetime import datetime
from functools import wraps

from flask import (
    Flask, jsonify, request, render_template, send_from_directory
)
from werkzeug.utils import secure_filename
from jinja2 import TemplateNotFound

# -----------------------------------------------------------------------------
# App & config
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
logging.basicConfig(level=logging.INFO)

API_TOKEN = os.environ.get("API_TOKEN", "").strip()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def require_token(f):
    """Bearer <API_TOKEN> auth for protected routes."""
    @wraps(f)
    def _wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        ok = False
        if auth.lower().startswith("bearer "):
            supplied = auth.split(" ", 1)[1].strip()
            ok = API_TOKEN and supplied == API_TOKEN
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return _wrap


def _routes():
    """Describe your protected API surface for quick introspection."""
    return [
        {"rule": "/__routes", "methods": ["GET"], "protected": True},
        {"rule": "/chat", "methods": ["POST"], "protected": True},
        {"rule": "/data/upload", "methods": ["POST"], "protected": True},
        {"rule": "/health", "methods": ["GET"], "protected": False},
        {"rule": "/", "methods": ["GET"], "protected": False},
    ]

# -----------------------------------------------------------------------------
# Public routes (no auth)
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    """Serve chat UI; fall back to inline page if template is missing."""
    try:
        return render_template("chat.html")
    except TemplateNotFound:
        return """
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Friday — quick test</title></head>
<body style="font-family:system-ui,Arial,sans-serif;max-width:720px;margin:40px auto;">
  <h1>Friday test</h1>
  <p>Paste your API token, then send a message to <code>/chat</code>.</p>
  <label>API token: <input id="t" style="width:420px"></label>
  <br><br>
  <textarea id="m" rows="3" style="width:100%;" placeholder="Hello Friday!"></textarea><br><br>
  <button id="go">Send</button>
  <pre id="out" style="background:#111;color:#0f0;padding:12px;white-space:pre-wrap"></pre>
<script>
const out = document.getElementById('out');
document.getElementById('go').onclick = async () => {
  const token = document.getElementById('t').value.trim();
  const msg   = document.getElementById('m').value || "Hello Friday!";
  out.textContent = "Sending...";
  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: {'Authorization':'Bearer '+token,'Content-Type':'application/json'},
      body: JSON.stringify({ message: msg })
    });
    out.textContent = await r.text();
  } catch (e) {
    out.textContent = 'Error: ' + e;
  }
};
</script>
</body>
</html>
""", 200


@app.route("/health")
def health():
    """Public healthcheck used by you (and optionally by Render)."""
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": bool(API_TOKEN)
    }), 200


# -----------------------------------------------------------------------------
# Protected API routes
# -----------------------------------------------------------------------------
@app.route("/__routes")
@require_token
def routes():
    return jsonify({"ok": True, "routes": _routes()}), 200


@app.route("/chat", methods=["POST"])
@require_token
def chat():
    """
    Minimal sample chat handler.
    Replace the echo with your model/tool logic as needed.
    """
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "message is required"}), 400

    # Example reply (replace with LLM or your pipeline)
    reply = f"Friday heard: {msg}"
    return jsonify({"ok": True, "reply": reply}), 200


@app.route("/data/upload", methods=["POST"])
@require_token
def data_upload():
    """
    Accepts multipart/form-data:
      - file   : uploaded file
      - notes  : optional text field
    Saves a copy to /tmp/uploads and returns metadata.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    f = request.files["file"]
    notes = request.form.get("notes", "")

    filename = secure_filename(f.filename or "upload.bin")
    up_dir = "/tmp/uploads"
    os.makedirs(up_dir, exist_ok=True)
    saved_path = os.path.join(up_dir, filename)
    f.save(saved_path)

    size = os.path.getsize(saved_path)
    return jsonify({
        "ok": True,
        "notes": notes,
        "bytes": size,
        "saved_as": saved_path.replace("\\", "/"),
        "server_time_utc": datetime.utcnow().isoformat() + "Z"
    }), 200


# -----------------------------------------------------------------------------
# Global error logging (nicer messages in logs)
# -----------------------------------------------------------------------------
@app.errorhandler(Exception)
def on_any_error(err):
    app.logger.exception("Unhandled error")
    # keep body simple to avoid leaking internals
    return jsonify({"ok": False, "error": "Internal error"}), 500


# -----------------------------------------------------------------------------
# Entrypoint (local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)















































