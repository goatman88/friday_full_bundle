import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load API token from environment
API_TOKEN = os.getenv("API_TOKEN", "changeme")  # Default fallback if not set

@app.before_request
def check_api_token():
    # Skip health check so Render can run it
    if request.path == "/health":
        return
    token = request.headers.get("X-API-TOKEN")
    if token != API_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

@app.route("/")
def root():
    return jsonify({"ok": True, "msg": "Friday backend online"})

@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": True if API_TOKEN else False
    })

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    return jsonify({"ok": True, "reply": f"Friday heard: {message}"})

@app.route("/data/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    notes = request.form.get("notes", "")
    if not file:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    # Save temporarily
    save_path = os.path.join("/tmp", file.filename)
    file.save(save_path)

    return jsonify({
        "ok": True,
        "notes": notes,
        "saved_as": save_path,
        "bytes": os.path.getsize(save_path)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))













































