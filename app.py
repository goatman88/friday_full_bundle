import os
import time
import json
import mimetypes
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ---------- Config ----------
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
MAX_BYTES = MAX_MB * 1024 * 1024

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")  # optional (chat falls back to local if missing)

API_TOKEN = os.environ.get("API_TOKEN")  # optional; if set, requests must include Bearer token

# ---------- App ----------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES
CORS(app)  # permissive CORS for now

# ---------- Helpers ----------
def utc_iso():
    return datetime.now(timezone.utc).isoformat()

def require_auth():
    """Return a response if auth fails; otherwise None."""
    if not API_TOKEN:
        return None  # auth not enforced
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(ok=False, error="Missing Bearer token"), 401
    token = auth.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        return jsonify(ok=False, error="Invalid token"), 403
    return None

# ---------- Routes ----------
@app.get("/")
def root():
    return jsonify(ok=True, msg="Friday backend online")

@app.get("/health")
def health():
    return jsonify(
        ok=True,
        status="running",
        debug={"key_present": bool(OPENAI_KEY), "model": OPENAI_MODEL}
    )

@app.post("/chat")
def chat():
    # auth (if enabled)
    fail = require_auth()
    if fail: return fail

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(ok=False, error="Missing 'message' in JSON body"), 400

    # Try OpenAI live; otherwise return a fast local answer
    if OPENAI_KEY:
        try:
            # OpenAI >= 1.0 client
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are Friday—succinct and practical."},
                    {"role": "user", "content": message}
                ],
                temperature=0.2,
            )
            text = resp.choices[0].message.content
            return jsonify(ok=True, reply=text, used_openai=True)
        except Exception as e:
            return jsonify(ok=True, reply=f"(OpenAI error: {e})\n\nLocal tip: {message}", used_openai=False)

    # Fallback local reply
    plan = "break the problem into 3–5 concrete steps.\nPrioritize the highest-leverage step first.\nRetest/measure after each step and iterate."
    return jsonify(ok=True, reply=f"OpenAI unavailable; giving a fast local answer.\n\nProblem summary: {message}\n\nPlan: {plan}", used_openai=False)

@app.post("/data/upload")
def data_upload():
    # auth (if enabled)
    fail = require_auth()
    if fail: return fail

    # file can be optional; allow notes-only uploads
    file = request.files.get("file")
    notes = request.form.get("notes", "")

    saved_name = None
    saved_bytes = 0
    mime = None

    if file:
        # Any extension allowed; sanitize filename
        original = secure_filename(file.filename or "file")
        stamp = int(time.time())
        saved_name = f"{stamp}_{original}"
        dest_path = UPLOAD_DIR / saved_name

        # Save
        file.save(dest_path)

        # Metadata
        saved_bytes = dest_path.stat().st_size
        mime = mimetypes.guess_type(dest_path.name)[0]

        if saved_bytes > MAX_BYTES:
            dest_path.unlink(missing_ok=True)
            return jsonify(ok=False, error=f"File exceeds {MAX_MB} MB limit"), 413

    return jsonify(
        ok=True,
        notes=notes,
        bytes=saved_bytes,
        mime=mime,
        saved_as=saved_name,
        server_time_utc=utc_iso()
    )

@app.get("/data/list")
def data_list():
    # auth (if enabled)
    fail = require_auth()
    if fail: return fail

    items = []
    for p in sorted(UPLOAD_DIR.glob("*")):
        if p.is_file():
            items.append({
                "name": p.name,
                "bytes": p.stat().st_size,
                "mime": mimetypes.guess_type(p.name)[0]
            })
    return jsonify(ok=True, files=items)

# Optional: serve saved files (debug/testing)
@app.get("/data/files/<path:filename>")
def data_files(filename):
    # auth (if enabled)
    fail = require_auth()
    if fail: return fail
    return send_from_directory(str(UPLOAD_DIR), filename, as_attachment=False)

# Debug route from your earlier checks
@app.get("/__routes")
def list_routes():
    from flask import current_app
    rules = []
    for r in current_app.url_map.iter_rules():
        if r.endpoint == "static":  # ignore Flask static
            continue
        methods = sorted([m for m in r.methods if m in {"GET", "POST", "PUT", "DELETE", "PATCH"}])
        rules.append({"rule": str(r), "methods": methods})
    return jsonify(ok=True, routes=rules)

# Entry
if __name__ == "__main__":
    # For local dev only
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))












































