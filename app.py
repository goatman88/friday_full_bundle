# app.py  (V7)
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.get("/")
def root():
    return jsonify({"ok": True, "message": "Friday API is up", "version": "V7"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running", "version": "V7"})

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "message is required"}), 400
    return jsonify({"ok": True, "reply": f"You said: {msg}", "version": "V7"})

@app.post("/data/upload")
def data_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400
    os.makedirs("/tmp/uploads", exist_ok=True)
    path = os.path.join("/tmp/uploads", f.filename)
    f.save(path)
    return jsonify({"ok": True, "saved": path, "size_bytes": os.path.getsize(path), "version": "V7"})

@app.get("/__routes")
def list_routes():
    routes = []
    for r in app.url_map.iter_rules():
        routes.append({"rule": str(r), "endpoint": r.endpoint,
                       "methods": sorted(m for m in r.methods if m not in {"HEAD","OPTIONS"})})
    return jsonify({"ok": True, "routes": routes, "version": "V7"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)







































