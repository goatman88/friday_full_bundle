# app.py
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, abort

# ---- Flask setup ------------------------------------------------------------
# Serve files from ./static at /static/* and allow send_from_directory to find them
app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---- Helpers ----------------------------------------------------------------
def _require_auth():
    """Return (ok: bool, error: str). Checks Authorization: Bearer <token>."""
    server_token = os.getenv("API_TOKEN", "")
    if not server_token:
        return False, "Server missing API_TOKEN"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False, "Missing Bearer token"
    token = auth.split(" ", 1)[1].strip()
    if token != server_token:
        return False, "Invalid token"
    return True, ""


def _json_unauthorized(msg="Unauthorized"):
    return jsonify({"ok": False, "error": msg}), 401


# ---- Basic pages ------------------------------------------------------------
@app.get("/")
def landing_page():
    # Serve your landing page (static/index.html)
    return send_from_directory(app.static_folder, "index.html")


@app.get("/docs")
def docs_page():
    # Tiny docs page (static/docs.html)
    return send_from_directory(app.static_folder, "docs.html")


@app.get("/ui")
def ui_page():
    # Browser chat UI (static/ui.html)
    return send_from_directory(app.static_folder, "ui.html")


# ---- Service health ---------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": bool(os.getenv("API_TOKEN", "")),
        "time": datetime.now(timezone.utc).isoformat()
    })


# ---- Introspection (protected) ----------------------------------------------
@app.get("/__routes")
def list_routes():
    ok, err = _require_auth()
    if not ok:
        return _json_unauthorized(err)

    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "rule": str(rule),
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            "endpoint": rule.endpoint,
        })
    return jsonify({"ok": True, "routes": routes})


# ---- Chat (protected) -------------------------------------------------------
@app.post("/chat")
def chat():
    ok, err = _require_auth()
    if not ok:
        return _json_unauthorized(err)

    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "message is required"}), 400

    # Your real logic would go here
    reply = f"Friday heard: {msg}"
    return jsonify({"ok": True, "reply": reply})


# ---- Upload (protected) -----------------------------------------------------
@app.post("/data/upload")
def data_upload():
    ok, err = _require_auth()
    if not ok:
        return _json_unauthorized(err)

    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    # Consume the stream (don’t persist for now)
    _ = file.read()  # bytes; discard
    notes = request.form.get("notes", "")

    return jsonify({"ok": True, "filename": file.filename, "notes": notes})


# ---- Static fallbacks (optional niceties) -----------------------------------
# If someone hits /favicon.ico or /robots.txt and you included them in static/
@app.get("/favicon.ico")
def favicon():
    try:
        return send_from_directory(app.static_folder, "favicon.ico")
    except Exception:
        abort(404)


@app.get("/robots.txt")
def robots():
    try:
        return send_from_directory(app.static_folder, "robots.txt")
    except Exception:
        abort(404)


# ---- Entrypoint for Render/Waitress -----------------------------------------
# Render runs `waitress-serve --listen=0.0.0.0:$PORT app:app`
# so we don't need app.run() here. It’s harmless locally though.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)


















































