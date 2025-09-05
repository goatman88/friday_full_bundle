from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "message": "Friday is live"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "running"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    return jsonify({"ok": True, "reply": f"You said: {message}"})

@app.route("/data/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    f = request.files["file"]
    # We accept any file type; just echo back the name for now.
    return jsonify({"ok": True, "filename": f.filename})

# helper to debug 404s
@app.route("/__routes", methods=["GET"])
def routes():
    rules = []
    for r in app.url_map.iter_rules():
        rules.append({"rule": str(r), "methods": sorted(list(r.methods - {'HEAD', 'OPTIONS'}))})
    return jsonify({"ok": True, "routes": rules})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)









































