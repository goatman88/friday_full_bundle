import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

# --- App setup ---
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# storage for uploads (Render's ephemeral disk is fine for small tests)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Model choice & key presence (for your /health quick check)
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

@app.get("/")
def root():
    return jsonify({"ok": True, "msg": "Friday backend online"}), 200

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "debug": {
            "key_present": OPENAI_KEY_PRESENT,
            "model": OPENAI_MODEL_DEFAULT
        }
    }), 200

@app.get("/__routes")
def list_routes():
    # simple router introspection for debugging
    rules = []
    for r in app.url_map.iter_rules():
        rules.append({"methods": sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")),
                      "rule": str(r)})
    return jsonify({"ok": True, "routes": rules}), 200

@app.post("/chat")
def chat():
    """
    Minimal chat echo so you can verify POST JSON quickly from Postman.
    If OpenAI key is present, you can wire your model call here later.
    """
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "Missing 'message' in JSON body"}), 400

    # (local fast reply so tests always succeed)
    reply = (
        "OpenAI unavailable; giving a fast local answer.\n\n"
        "Problem summary: " + msg + "\n"
        "Plan: break the problem into 3–5 concrete steps.\n"
        "Prioritize the highest-leverage step first.\n"
        "Retest/measure after each step and iterate."
    )
    return jsonify({"ok": True, "used_openai": False, "reply": reply}), 200

@app.post("/data/upload")
def data_upload():
    """
    Accept ANY file type via multipart/form-data.
    Keys:
      - file: (required) the actual file
      - notes: (optional) free text
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No 'file' part in form-data"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    notes = request.form.get("notes", "")
    # keep extension, sanitize basename
    filename = secure_filename(f.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_name = f"{timestamp}__{filename}"
    out_path = os.path.join(UPLOAD_DIR, out_name)
    f.save(out_path)

    info = {
        "ok": True,
        "saved_as": out_name,
        "bytes": os.path.getsize(out_path),
        "notes": notes,
        "server_time_utc": timestamp
    }
    return jsonify(info), 200

# Optional: friendlier 404 so it's obvious what path was hit
@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "Not Found", "path": request.path}), 404

# For local debug: `python app.py`
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)











































