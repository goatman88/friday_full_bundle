# app.py
import os
import io
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template, send_from_directory, abort
)
from werkzeug.utils import secure_filename

# ── Flask setup ────────────────────────────────────────────────────────────────
# Looks in ./static and ./templates automatically
app = Flask(__name__, static_folder="static", template_folder="templates")

# Single source of truth for your API token (set in Render env)
API_TOKEN = os.getenv("API_TOKEN", "").strip()

# Where uploads are written (Render’s ephemeral disk, OK for demos)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _auth_ok(req: request) -> bool:
    """
    Require: Authorization: Bearer <API_TOKEN>
    """
    if not API_TOKEN:
        # If you forgot to set it in Render, allow nothing but report clearly.
        return False
    auth = req.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    return token == API_TOKEN


def _require_auth():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    """
    Quick health probe used by you (and can be used by Render).
    """
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": bool(API_TOKEN),
        "time": datetime.utcnow().isoformat() + "Z",
    })


@app.route("/__routes", methods=["GET"])
def list_routes():
    """
    Lists available routes (auth required).
    """
    auth = _require_auth()
    if auth:
        return auth  # 401

    routes = []
    for rule in app.url_map.iter_rules():
        # Skip static file automatic endpoint to keep it tidy
        if rule.endpoint == "static":
            continue
        routes.append({
            "rule": str(rule),
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            "endpoint": rule.endpoint
        })
    return jsonify({"ok": True, "routes": routes})


@app.route("/", methods=["GET"])
def index():
    """
    Home page. If templates/index.html exists we render it;
    otherwise we show a tiny JSON so deploys never 500 on '/'.
    """
    # Try to render a template if present
    tpl_path = os.path.join(app.template_folder or "templates", "index.html")
    if os.path.exists(tpl_path):
        return render_template("index.html")
    # Minimal fallback
    return jsonify({
        "ok": True,
        "message": "Friday backend is up. Add templates/index.html for a homepage."
    })


@app.route("/chat", methods=["POST"])
def chat():
    """
    Echo-style chat endpoint (auth required).
    Body: { "message": "Hello Friday!" }
    """
    auth = _require_auth()
    if auth:
        return auth  # 401

    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "Missing 'message'"}), 400

    # In your real app, call your LLM or business logic here.
    return jsonify({"ok": True, "reply": f"Friday heard: {msg}"})


@app.route("/data/upload", methods=["POST"])
def upload():
    """
    Multipart file upload (auth required).
    Expect: part name 'file' (+ optional 'notes')
    """
    auth = _require_auth()
    if auth:
        return auth  # 401

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    filename = secure_filename(f.filename)
    save_path = os.path.join(UPLOAD_DIR, filename)

    # Save to disk (Render’s ephemeral storage—fine for testing)
    # If you don’t want to persist, you could read bytes = f.read() and process in-memory.
    f.save(save_path)

    notes = request.form.get("notes", "")

    return jsonify({
        "ok": True,
        "filename": filename,
        "bytes": os.path.getsize(save_path),
        "notes": notes,
        "saved_to": save_path
    })


# (Optional) serve a favicon if you drop one in static/
@app.route("/favicon.ico")
def favicon():
    path = app.static_folder or "static"
    file_path = os.path.join(path, "favicon.ico")
    if os.path.exists(file_path):
        return send_from_directory(path, "favicon.ico")
    abort(404)

from flask import send_from_directory

@app.get("/ui")
def friday_ui():
    # serves /static/friday/ui.html
    return send_from_directory("static/friday", "ui.html")

# ── Entrypoint for local dev (Render uses Procfile's waitress) ────────────────
if __name__ == "__main__":
    # For local dev/tests only; on Render you run via Procfile:  waitress-serve app:app
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
















































