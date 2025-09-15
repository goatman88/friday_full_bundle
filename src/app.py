import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from s3_uploads import upload_file_to_s3

app = Flask(__name__)
CORS(app)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "running"})

@app.route("/routes", methods=["GET"])
def routes():
    output = []
    for rule in app.url_map.iter_rules():
        methods = ",".join(sorted(rule.methods))
        output.append({"path": str(rule), "methods": methods})
    return jsonify(output)

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400

    file = request.files["file"]
    bucket = os.getenv("S3_BUCKET")

    if not bucket:
        return jsonify({"error": "missing S3_BUCKET env var"}), 500

    url = upload_file_to_s3(file, bucket)
    return jsonify({"success": True, "url": url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)










































































