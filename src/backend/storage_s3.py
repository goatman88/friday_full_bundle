# src/backend/storage_s3.py
from __future__ import annotations

import os
import uuid
import boto3
from botocore.client import Config

# --- Required env vars ---
# AWS_ACCESS_KEY_ID
# AWS_SECRET_ACCESS_KEY
# AWS_DEFAULT_REGION (e.g., us-east-1)
# S3_BUCKET
# Optional: S3_PREFIX (defaults to "uploads/")

_bucket = os.environ.get("S3_BUCKET")
_prefix = os.environ.get("S3_PREFIX", "uploads/")
_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

if not _bucket:
    raise RuntimeError("S3_BUCKET is not set")

# Build client explicitly from env (so boto3 doesn't pick up partial creds)
_s3 = boto3.client(
    "s3",
    region_name=_region,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)


def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """
    Upload raw bytes to S3 with a unique prefix. Returns an s3:// URI used elsewhere in the app.
    """
    key = f"{_prefix.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    _s3.put_object(Bucket=_bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{_bucket}/{key}"


def presign_get_url(s3_uri: str, expires_seconds: int = 600) -> str:
    """
    Create a presigned HTTPS GET URL for an s3://bucket/key URI.
    The object does NOT need to exist to generate the URL.
    """
    if not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
        raise ValueError("presign_get_url: expected s3_uri like 's3://bucket/key'")

    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    if not bucket or not key:
        raise ValueError("presign_get_url: malformed s3_uri (bucket/key missing)")

    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


# (Optional) If you later want direct browser uploads, uncomment and use:
# def presign_put_url(key: str, content_type: str = "application/octet-stream", expires_seconds: int = 600) -> str:
#     """
#     Create a presigned HTTPS PUT URL for uploading directly from the client.
#     Key should be a path like 'uploads/uuid-filename.ext'.
#     """
#     return _s3.generate_presigned_url(
#         "put_object",
#         Params={"Bucket": _bucket, "Key": key, "ContentType": content_type},
#         ExpiresIn=expires_seconds,
#     )


