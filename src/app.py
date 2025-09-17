# src/app.py
import os
import uuid
from datetime import timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS

# ---- Flask app (Render imports this symbol) ----
app = Flask(__name__)
CORS(app)

# ---- Config / AWS client (lazy so missing creds don't crash /health) ----
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = (os.getenv("S3_PREFIX") or "uploads").strip("/")

def _s3():
    # Lazy import so the app can boot even if boto3 isn't installed properly
    import boto3  # type: ignore
    return boto3.client("s3", region_name=AWS_REGION)

# ---------- Health ----------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "friday-rag-backend"}), 200

@app.route("/api/health/s3", methods=["GET"])
def health_s3():
    try:
        if not (AWS_REGION and S3_BUCKET):
            return jsonify({"ok": False, "error": "Missing AWS_REGION or S3_BUCKET"}), 400
        _s3().list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        return jsonify({"ok": True, "bucket": S3_BUCKET, "region": AWS_REGION}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------- RAG: Step 2 – presign upload ----------
@app.route("/api/rag/upload_url", methods=["POST"])
def presign_upload():
    """
    Body: { "filename": "demo.txt", "content_type": "text/plain" }
    Returns: { put_url, s3_uri, get_url, expires_sec }
    """
    body = request.get_json(force=True, silent=True) or {}
    filename = body.get("filename") or f"file-{uuid.uuid4().hex}"
    content_type = body.get("content_type") or "application/octet-stream"

    if not (AWS_REGION and S3_BUCKET):
        return jsonify({"error": "Server missing AWS_REGION or S3_BUCKET"}), 500

    key = f"{S3_PREFIX}/{uuid.uuid4().hex}/{filename}"
    expires = int(timedelta(minutes=10).total_seconds())

    try:
        s3 = _s3()
        put_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )
        s3_uri = f"s3://{S3_BUCKET}/{key}"
        get_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"
        return jsonify(
            {
                "put_url": put_url,
                "s3_uri": s3_uri,
                "get_url": get_url,
                "expires_sec": expires,
            }
        )
    except Exception as e:
        return jsonify({"error": f"presign failed: {e}"}), 500

# ---------- RAG: Step 3 – confirm/index (stub) ----------
@app.route("/api/rag/confirm_upload", methods=["POST"])
def confirm_upload():
    """
    Body example you’ve been sending:
    {
      "s3_uri": "s3://bucket/path/demo.txt",
      "title": "Demo file",
      "external_id": "demo_1",
      "metadata": {"collection": "default", "tags": ["test"], "source": "cli"},
      "chunk": {"size": 1200, "overlap": 150}
    }
    This stub just acknowledges with a fake document id.
    """
    body = request.get_json(force=True, silent=True) or {}
    s3_uri = body.get("s3_uri")
    if not s3_uri:
        return jsonify({"error": "s3_uri is required"}), 400

    doc_id = uuid.uuid4().hex
    # TODO: download from S3 and index your content here.
    return jsonify({"status": "indexed", "doc_id": doc_id, "received": body}), 200

# ---------- RAG: Step 4 – query (stub) ----------
@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    """
    Body: { "q": "what did the fox do?" }
    Returns a stub response so your PS step doesn't 404.
    """
    body = request.get_json(force=True, silent=True) or {}
    q = body.get("q") or ""
    return jsonify(
        {
            "query": q,
            "answers": [
                {
                    "text": "Indexing stub is active. Replace with your vector search results.",
                    "score": 0.0,
                    "source": None,
                }
            ],
        }
    ), 200

# ---------- Optional docs hint ----------
@app.route("/api", methods=["GET"])
def api_root():
    return jsonify(
        {
            "ok": True,
            "endpoints": [
                "GET /api/health",
                "GET /api/health/s3",
                "POST /api/rag/upload_url",
                "POST /api/rag/confirm_upload",
                "POST /api/rag/query",
            ],
        }
    )

# Local dev
if __name__ == "__main__":
    # When running locally: python src/app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))




















































































