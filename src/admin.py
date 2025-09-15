from __future__ import annotations
import math
from flask import Blueprint, jsonify, request, render_template, abort
from werkzeug.exceptions import BadRequest
from .settings import ADMIN_TOKEN, S3_BUCKET, MAX_UPLOAD_MB
from .s3_uploads import create_multipart, presign_part_urls, complete_multipart

bp = Blueprint("admin", __name__)

def _require_admin(req: request):
    tok = req.headers.get("x-admin-token") or req.args.get("admin_token")
    if not ADMIN_TOKEN or tok != ADMIN_TOKEN:
        abort(401)

@bp.get("/admin")
def admin_ui():
    _require_admin(request)
    return render_template("admin.html", bucket=S3_BUCKET, max_mb=MAX_UPLOAD_MB)

@bp.post("/api/uploads/init")
def api_uploads_init():
    _require_admin(request)
    j = request.get_json(force=True, silent=True) or {}
    key = j.get("key")
    ctype = j.get("content_type", "application/octet-stream")
    total_size = int(j.get("total_size") or 0)

    if not key:
        raise BadRequest("key required")
    if total_size and total_size > MAX_UPLOAD_MB * 1024 * 1024:
        raise BadRequest(f"Max file size {MAX_UPLOAD_MB}MB")

    upload_id = create_multipart(key, ctype)

    # decide chunk size (e.g. 8MB) and how many parts the client should use
    chunk_size = 8 * 1024 * 1024
    part_count = max(1, math.ceil(total_size / chunk_size)) if total_size else 50  # default budget
    parts = list(range(1, part_count + 1))
    urls = presign_part_urls(key, upload_id, parts)
    return jsonify({"ok": True, "key": key, "upload_id": upload_id, "parts": urls, "chunk_size": chunk_size})

@bp.post("/api/uploads/complete")
def api_uploads_complete():
    _require_admin(request)
    j = request.get_json(force=True, silent=True) or {}
    key = j.get("key")
    upload_id = j.get("upload_id")
    parts = j.get("parts")  # [{partNumber, etag}]
    if not (key and upload_id and parts):
        raise BadRequest("key, upload_id, parts required")

    # normalize payload to botocore shape
    final_parts = [{"PartNumber": int(p["partNumber"]), "ETag": p["etag"]} for p in parts]
    result = complete_multipart(key, upload_id, final_parts)
    return jsonify(result)

# Example: hook upload->index for your RAG (optional placeholder)
@bp.post("/api/admin/index")
def api_admin_index():
    _require_admin(request)
    j = request.get_json(force=True, silent=True) or {}
    # TODO integrate with your existing /api/rag/index logic (call it internally)
    # Here we simply echo
    return jsonify({"ok": True, "received": j})
