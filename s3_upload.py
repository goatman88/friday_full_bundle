# src/s3_uploads.py
import os, time, re, uuid
from datetime import timedelta
from flask import Blueprint, request, jsonify
from botocore.config import Config
import boto3

bp_s3 = Blueprint("s3_uploads", __name__, url_prefix="/api/s3")

# --- configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ["S3_BUCKET"]
AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT")  # optional for S3-compatible
SIGNED_TTL_SEC = int(os.getenv("S3_SIGNED_TTL_SEC", "900"))  # 15 min default

# optional: restrict where uploads come from
ALLOWED_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

# ---- helpers ----
def s3_client():
    cfg = Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"})
    kw = dict(region_name=AWS_REGION, config=cfg)
    if AWS_S3_ENDPOINT:
        kw["endpoint_url"] = AWS_S3_ENDPOINT
    # Credentials are automatically picked from env by boto3; no need to pass explicitly.
    return boto3.client("s3", **kw)

SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._\-\/]+")

def safe_key_from_filename(filename: str) -> str:
    # Put files under a date/user-ish prefix; keep it deterministic
    base = SAFE_KEY_RE.sub("_", filename.strip()) or f"file_{uuid.uuid4().hex}"
    ymd = time.strftime("%Y/%m/%d")
    return f"uploads/{ymd}/{uuid.uuid4().hex}/{base}"

def json_error(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

# ---- routes ----

@bp_s3.after_request
def add_cors_headers(resp):
    # Respect FRONTEND_ORIGIN when set, otherwise allow all (use only for local testing)
    resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp

@bp_s3.route("/presign", methods=["POST", "OPTIONS"])
def presign_put():
    """
    For small files: returns a single presigned PUT url.
    Body: { "filename": "...", "contentType": "mime/type" }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(force=True, silent=True) or {}
    filename = data.get("filename") or "upload.bin"
    ctype = data.get("contentType") or "application/octet-stream"
    key = safe_key_from_filename(filename)
    s3 = s3_client()
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": ctype},
        ExpiresIn=SIGNED_TTL_SEC,
    )
    return jsonify({"ok": True, "bucket": S3_BUCKET, "key": key, "url": url, "expiresIn": SIGNED_TTL_SEC})

@bp_s3.route("/uploads/init", methods=["POST", "OPTIONS"])
def init_multipart():
    """
    Start multipart upload.
    Body: { "filename": "...", "contentType": "mime/type", "metadata": {optional kv} }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(force=True, silent=True) or {}
    filename = data.get("filename") or "upload.bin"
    ctype = data.get("contentType") or "application/octet-stream"
    metadata = data.get("metadata") or {}
    key = safe_key_from_filename(filename)

    s3 = s3_client()
    resp = s3.create_multipart_upload(Bucket=S3_BUCKET, Key=key, ContentType=ctype, Metadata=metadata)
    upload_id = resp["UploadId"]
    return jsonify({"ok": True, "bucket": S3_BUCKET, "key": key, "uploadId": upload_id, "expiresIn": SIGNED_TTL_SEC})

@bp_s3.route("/uploads/sign", methods=["GET", "OPTIONS"])
def sign_part():
    """
    Sign a part.
    Query: ?key=...&uploadId=...&partNumber=1
    Returns: { url }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    key = request.args.get("key")
    upload_id = request.args.get("uploadId")
    try:
        part_number = int(request.args.get("partNumber", ""))
    except ValueError:
        return json_error("partNumber must be an integer", 400)

    if not key or not upload_id:
        return json_error("key and uploadId are required", 400)

    s3 = s3_client()
    url = s3.generate_presigned_url(
        "upload_part",
        Params={"Bucket": S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
        ExpiresIn=SIGNED_TTL_SEC,
    )
    return jsonify({"ok": True, "url": url, "expiresIn": SIGNED_TTL_SEC})

@bp_s3.route("/uploads/complete", methods=["POST", "OPTIONS"])
def complete_multipart():
    """
    Complete multipart upload.
    Body: { "key": "...", "uploadId": "...", "parts": [ { "ETag": "...", "PartNumber": 1 }, ... ] }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(force=True, silent=True) or {}
    key = data.get("key")
    upload_id = data.get("uploadId")
    parts = data.get("parts") or []
    if not key or not upload_id or not parts:
        return json_error("key, uploadId, and parts are required", 400)

    # Sort parts by part number just in case
    parts_sorted = sorted(parts, key=lambda p: int(p["PartNumber"]))
    s3 = s3_client()
    resp = s3.complete_multipart_upload(
        Bucket=S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts_sorted},
    )
    location = resp.get("Location") or f"s3://{S3_BUCKET}/{key}"
    etag = resp.get("ETag")
    return jsonify({"ok": True, "bucket": S3_BUCKET, "key": key, "etag": etag, "location": location})

@bp_s3.route("/uploads/abort", methods=["POST", "OPTIONS"])
def abort_multipart():
    """
    Abort multipart upload.
    Body: { "key": "...", "uploadId": "..." }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(force=True, silent=True) or {}
    key = data.get("key")
    upload_id = data.get("uploadId")
    if not key or not upload_id:
        return json_error("key and uploadId are required", 400)

    s3 = s3_client()
    s3.abort_multipart_upload(Bucket=S3_BUCKET, Key=key, UploadId=upload_id)
    return jsonify({"ok": True})
