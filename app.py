import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

# Where uploads will be stored on Render (ephemeral but fine for testing)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MODEL_FALLBACK = os.environ.get("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")

# ── Helpers ───────────────────────────────────────────────────────────────────
def ok(payload: dict, code: int = 200):
    return jsonify({"ok": True, **payload}), code

def err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return ok({"message": "Friday is live. Try GET /health, POST /chat, POST /data/upload"})

@app.route("/health", methods=["GET"])
def health():
    # also tells you if the OPENAI_API_KEY is present (without leaking it)
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    return ok({"status": "running", "debug": {"key_present": key_present, "model": MODEL_FALLBACK}})

@app.route("/chat", methods=["POST"])
def chat():
    # Expect: {"message": "..."}
    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return err("Body must be JSON like {\"message\": \"...\"}", 415)

    user_msg = (body.get("message") or "").strip()
    if not user_msg:
        return err("Missing 'message'.")

    # Simple, local “Einstein-y” scaffolding when OpenAI isn’t used
    reply = (
        "OpenAI unavailable; giving a fast local answer.\n\n"
        "Problem summary: " + user_msg + "\n"
        "Plan: break the problem into 3–5 concrete steps.\n"
        "Prioritize the highest-leverage step first.\n"
        "Retest/measure after each step and iterate."
    )
    return ok({"reply": reply, "used_openai": False})

@app.route("/data/upload", methods=["POST"])
def data_upload():
    """
    Accepts ANY file type via multipart/form-data with key 'file'.
    Optional form fields:
      - notes: free text
    Saves file under data/uploads/<timestamp>_<original_name>
    Returns file metadata.
    """
    if "file" not in request.files:
        return err("Send multipart/form-data with key 'file'." , 415)

    f = request.files["file"]
    if f.filename == "":
        return err("Empty filename.")

    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe_name = f.filename.replace("/", "_").replace("\\", "_")
    save_as = f"{ts}_{safe_name}"
    save_path = os.path.join(UPLOAD_DIR, save_as)
    f.save(save_path)

    meta = {
        "saved_as": save_as,
        "bytes": os.path.getsize(save_path),
        "mimetype": f.mimetype,
        "notes": request.form.get("notes") or "",
    }
    return ok({"file": meta}, 201)

@app.route("/__routes", methods=["GET"])
def list_routes():
    routes = []
    for r in app.url_map.iter_rules():
        routes.append({"rule": str(r), "methods": sorted(m for m in r.methods if m in {"GET","POST","PUT","PATCH","DELETE"})})
    return ok({"routes": routes})

# (optional) serve static files if needed
@app.route("/static/<path:filename>", methods=["GET"])
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # local run
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)










































