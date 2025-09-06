import os
from datetime import datetime
from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, Response
)

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

API_TOKEN = os.getenv("API_TOKEN", "").strip()
if not API_TOKEN:
    # Don’t crash on boot; /health will report key_present=false
    pass


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _auth_ok(req: request) -> bool:
    """Validate Bearer token in Authorization header."""
    hdr = req.headers.get("Authorization", "")
    if not hdr.lower().startswith("bearer "):
        return False
    token = hdr.split(" ", 1)[1].strip()
    return token == API_TOKEN and token != ""


def _unauthorized():
    return jsonify({"ok": False, "error": "Unauthorized"}), 401


# -----------------------------------------------------------------------------
# Health / Landing
# -----------------------------------------------------------------------------
@app.get("/health", endpoint="health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "time": datetime.utcnow().isoformat() + "Z",
        "key_present": bool(API_TOKEN),
    })


@app.get("/", endpoint="home_page")
def home_page():
    """
    Try to render templates/index.html if present; otherwise return a tiny page
    with links. Keep this lean so you can style the template separately.
    """
    try:
        return render_template("index.html")
    except Exception:
        html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Friday API</title></head>
<body style="font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Arial;padding:24px">
  <h1>🚀 Friday API is running</h1>
  <p>Quick links:</p>
  <ul>
    <li><a href="/ui">Browser Chat</a></li>
    <li><a href="/docs">Docs</a></li>
    <li><a href="/health">Health</a></li>
  </ul>
</body></html>"""
        return Response(html, mimetype="text/html")


# -----------------------------------------------------------------------------
# Minimal UI & Docs (served from /static)
# -----------------------------------------------------------------------------
@app.get("/ui", endpoint="ui_page")
def ui_page():
    # serves static/ui.html
    return send_from_directory("static", "ui.html")


@app.get("/docs", endpoint="docs_page")
def docs_page():
    # serves static/docs.html
    return send_from_directory("static", "docs.html")


# -----------------------------------------------------------------------------
# API: routes listing (auth)
# -----------------------------------------------------------------------------
@app.get("/__routes", endpoint="routes_list")
def routes_list():
    if not _auth_ok(request):
        return _unauthorized()

    out = []
    for rule in app.url_map.iter_rules():
        # Skip Flask internals
        if rule.endpoint == "static":
            continue
        out.append({
            "rule": str(rule),
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            "endpoint": rule.endpoint,
        })
    return jsonify({"ok": True, "routes": out})


# -----------------------------------------------------------------------------
# API: chat (auth)
# -----------------------------------------------------------------------------
@app.post("/chat", endpoint="chat")
def chat():
    if not _auth_ok(request):
        return _unauthorized()

    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Missing 'message'"}), 400

    # For now we just echo back. Wire your LLM/tooling here later.
    return jsonify({"ok": True, "reply": f"Friday heard: {message}"})


# -----------------------------------------------------------------------------
# API: data upload (auth; multipart/form-data)
# -----------------------------------------------------------------------------
@app.post("/data/upload", endpoint="upload_data")
def upload_data():
    if not _auth_ok(request):
        return _unauthorized()

    file = request.files.get("file")
    notes = request.form.get("notes", "")

    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    # We don’t persist on disk for now—just read size and acknowledge.
    # If you want to save, use a temp dir:
    #   tmp_path = os.path.join("/tmp", secure_filename(file.filename))
    #   file.save(tmp_path)
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)

    return jsonify({
        "ok": True,
        "filename": file.filename,
        "size_bytes": size,
        "notes": notes,
        "message": "Upload received",
    })


# -----------------------------------------------------------------------------
# Error handlers (nicer JSON for common API errors)
# -----------------------------------------------------------------------------
@app.errorhandler(405)
def method_not_allowed(e):
    # Keep HTML default for browser hits; JSON for API routes
    if request.path.startswith(("/chat", "/__routes", "/data/upload")):
        return jsonify({"ok": False, "error": "Method Not Allowed"}), 405
    return e


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith(("/chat", "/__routes", "/data/upload", "/health")):
        return jsonify({"ok": False, "error": "Not Found"}), 404
    return e


# -----------------------------------------------------------------------------
# Entry point for local dev (Render will use the WSGI app: app:app)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Use PORT env if present (Render/Heroku convention)
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

















































