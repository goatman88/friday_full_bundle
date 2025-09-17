from flask import Flask, request, jsonify

app = Flask(__name__)

# ----------------------------
# Health check route
# ----------------------------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ----------------------------
# RAG: confirm upload route
# ----------------------------
@app.route("/api/rag/confirm_upload", methods=["POST"])
def confirm_upload():
    data = request.get_json(silent=True) or {}
    return jsonify({
        "message": "confirm upload works",
        "received": data
    }), 200


# ----------------------------
# RAG: query route
# ----------------------------
@app.route("/api/rag/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    # Example: echo back the query text
    query_text = data.get("q", "No query provided")
    return jsonify({
        "message": "query works",
        "query_received": query_text
    }), 200


# ----------------------------
# Root route (optional)
# ----------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "Friday backend is live"}), 200


# ----------------------------
# Run locally
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)






















































































