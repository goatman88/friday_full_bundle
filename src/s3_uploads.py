from flask import Blueprint, request, jsonify
import boto3, os, json
from . import settings

s3_bp = Blueprint("s3", __name__)

def s3_client():
    return boto3.client(
        "s3",
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

@s3_bp.route("/sign", methods=["POST"])
def sign_put():
    body = request.get_json(force=True) or {}
    key = body.get("key")
    ctype = body.get("content_type") or "application/octet-stream"
    if not key: return jsonify(error="key required"), 400
    s3 = s3_client()
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key, "ContentType": ctype},
        ExpiresIn=600,
    )
    return jsonify(url=url, key=key)

# multipart
@s3_bp.route("/multipart/create", methods=["POST"])
def mp_create():
    body = request.get_json(force=True) or {}
    key = body.get("key")
    ctype = body.get("content_type") or "application/octet-stream"
    if not key: return jsonify(error="key required"), 400
    s3 = s3_client()
    r = s3.create_multipart_upload(Bucket=settings.S3_BUCKET, Key=key, ContentType=ctype)
    return jsonify(upload_id=r["UploadId"], key=key)

@s3_bp.route("/multipart/part", methods=["POST"])
def mp_part():
    body = request.get_json(force=True) or {}
    key = body.get("key"); upload_id = body.get("upload_id"); part_number = int(body.get("part_number") or 1)
    if not (key and upload_id and part_number): return jsonify(error="key, upload_id, part_number required"), 400
    s3 = s3_client()
    url = s3.generate_presigned_url(
        "upload_part",
        Params={"Bucket": settings.S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
        ExpiresIn=600,
    )
    return jsonify(url=url)

@s3_bp.route("/multipart/complete", methods=["POST"])
def mp_complete():
    body = request.get_json(force=True) or {}
    key = body.get("key"); upload_id = body.get("upload_id"); parts = body.get("parts") or []
    if not (key and upload_id and parts): return jsonify(error="key, upload_id, parts[] required"), 400
    s3 = s3_client()
    r = s3.complete_multipart_upload(
        Bucket=settings.S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )
    return jsonify(ok=True, location=r.get("Location"), etag=r.get("ETag"))




