# app.py  — minimal, production-safe, known-good
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# ---------- core sanity routes ----------
@app.get("/")
def root():
    return jsonify({"ok": True, "message": "Friday API is up"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "message is required"}), 400
    return jsonify({"ok": True, "reply": f"You said: {msg}"})

# ---------- accept-any-file uploads ----------
# form-data key: file (one file at a time for simplicity)
@app.post("/data/upload")
def data_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file part"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "empty filename"}), 400

    # save to /tmp (ephemeral on Render) — good for immediate processing
    os.makedirs("/tmp/uploads", exist_ok=True)
    save_path = os.path.join("/tmp/uploads", f.filename)
    f.save(save_path)

    # TODO: your processing/indexing goes here
    return jsonify({"ok": True, "saved": save_path, "size_bytes": os.path.getsize(save_path)})

# ---------- debug: list all registered routes ----------
@app.get("/__routes")
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "rule": str(rule),
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        })
    return jsonify({"ok": True, "routes": routes})

if __name__ == "__main__":
    # local run only
    app.run(host="127.0.0.1", port=5000, debug=True)






































