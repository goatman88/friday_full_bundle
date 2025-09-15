import os
from flask import Flask, jsonify, request
from flask_cors import CORS

# --- existing imports / your other modules here ---
# from rag import index_doc, query_rag ... (whatever you already had)
# Make sure this import exists now:
from s3_uploads import (
    initiate_multipart, sign_part, complete_multipart, abort_multipart, put_object_direct
)

app = Flask(__name__)

# CORS: allow your dev tools and any future frontend.
_frontend = os.environ.get("FRONTEND_ORIGIN")
if _frontend:
    CORS(app, origins=[_frontend])
else:
    # Dev-friendly, can tighten later
    CORS(app)

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

@app.get("/__routes")
def routes_list():
    rules = sorted([str(r.rule) for r in app.url_map.iter_rules()])
    return jsonify(rules)

# ------------- S3 UPLOADS -------------

@app.post("/s3/multipart/initiate")
def s3_multipart_initiate():
    data = request.get_json(force=True, silent=False)
    filename = data.get("filename")
    content_type = data.get("content_type", "application/octet-stream")
    user_id = data.get("user_id")
    if not filename:
        return jsonify({"ok": False, "error": "filename required"}), 400
    try:
        res = initiate_multipart(filename=filename, content_type=content_type, user_id=user_id)
        return jsonify({"ok": True, "upload_id": res.upload_id, "key": res.key})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/s3/multipart/sign")
def s3_multipart_sign():
    data = request.get_json(force=True, silent=False)
    key = data.get("key")
    upload_id = data.get("upload_id")
    part_number = int(data.get("part_number", 1))
    if not (key and upload_id and part_number >= 1):
        return jsonify({"ok": False, "error": "key, upload_id, part_number required"}), 400
    try:
        res = sign_part(key=key, upload_id=upload_id, part_number=part_number)
        return jsonify({"ok": True, **res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/s3/multipart/complete")
def s3_multipart_complete():
    data = request.get_json(force=True, silent=False)
    key = data.get("key")
    upload_id = data.get("upload_id")
    parts = data.get("parts")  # [{ETag, PartNumber}]
    if not (key and upload_id and parts):
        return jsonify({"ok": False, "error": "key, upload_id, parts required"}), 400
    try:
        res = complete_multipart(key=key, upload_id=upload_id, parts=parts)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.delete("/s3/multipart/abort")
def s3_multipart_abort():
    data = request.get_json(force=True, silent=False)
    key = data.get("key")
    upload_id = data.get("upload_id")
    if not (key and upload_id):
        return jsonify({"ok": False, "error": "key and upload_id required"}), 400
    try:
        res = abort_multipart(key=key, upload_id=upload_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/s3/upload")  # small direct (≤ MAX_DIRECT_MB)
def s3_small_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "multipart/form-data with 'file' required"}), 400
    f = request.files["file"]
    user_id = request.form.get("user_id")
    try:
        res = put_object_direct(filename=f.filename, stream=f.stream, content_type=f.mimetype or "application/octet-stream", user_id=user_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# --- keep your other API routes below ---
# e.g. /api/rag/index, /api/rag/query, etc.

if __name__ == "__main__":
    # Local run only
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))









































































