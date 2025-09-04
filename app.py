import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Optional: OpenAI if key is set
try:
    import openai
except ImportError:
    openai = None

# Flask app
app = Flask(__name__)
CORS(app)

# Upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Root route - no more 404 at base URL
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "ok": True,
        "message": "Welcome to Friday API 🚀. Use /health (GET), /chat (POST), or /data/upload (POST)."
    })

# Health check
@app.route("/health", methods=["GET"])
def health():
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    return jsonify({
        "ok": True,
        "status": "running",
        "debug": {
            "key_present": key_present,
            "model": os.environ.get("FRIDAY_MODEL", "gpt-4o-mini"),
        }
    })

# Chat endpoint
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"ok": False, "error": "Missing 'message'"}), 400

    # Default reply (local fallback)
    reply = f"You said: {user_message}"

    # If OpenAI key is present, try using OpenAI
    used_openai = False
    if openai and os.environ.get("OPENAI_API_KEY"):
        try:
            openai.api_key = os.environ["OPENAI_API_KEY"]
            response = openai.chat.completions.create(
                model=os.environ.get("FRIDAY_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": user_message}]
            )
            reply = response.choices[0].message.content.strip()
            used_openai = True
        except Exception as e:
            reply = f"(Fallback) OpenAI error: {str(e)}"

    return jsonify({
        "ok": True,
        "reply": reply,
        "used_openai": used_openai
    })

# File upload endpoint
@app.route("/data/upload", methods=["POST"])
def upload_data():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    return jsonify({
        "ok": True,
        "message": f"File '{filename}' uploaded successfully!",
        "path": filepath
    })

# Run locally
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)




































