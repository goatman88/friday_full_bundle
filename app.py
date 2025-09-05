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

    file = request.files["file"]
    filename = file.filename
    # For now, just return confirmation — extend later to process
    return jsonify({"ok": True, "filename": filename})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)








































