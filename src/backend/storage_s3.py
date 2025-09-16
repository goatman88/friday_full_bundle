# src/backend/storage_s3.py
from __future__ import annotations
import os, uuid
import boto3
from botocore.client import Config

# Required env vars:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - AWS_DEFAULT_REGION  (e.g., "us-east-1")
# - S3_BUCKET
# Optional: S3_PREFIX (defaults to "uploads/")

_BUCKET = os.environ.get("S3_BUCKET")
_PREFIX = os.environ.get("S3_PREFIX", "uploads/")
_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

if not _BUCKET:
    raise RuntimeError("S3_BUCKET is not set")

# Build client explicitly so boto3 doesn't pick up partial creds somewhere else
_S3 = boto3.client(
    "s3",
    region_name=_REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)

def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """
    Upload raw bytes to S3 under a unique key and return an s3:// URI.
    """
    key = f"{_PREFIX.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    _S3.put_object(Bucket=_BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"s3://{_BUCKET}/{key}"

def presign_get_url(s3_uri: str, expires_seconds: int = 600) -> str:
    """
    Create a presigned HTTPS GET URL from an s3://bucket/key URI.
    (The object does not need to exist to generate this URL.)
    """
    if not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
        raise ValueError("presign_get_url expects something like 's3://bucket/key'")

    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    if not bucket or not key:
        raise ValueError("presign_get_url: malformed s3_uri (missing bucket/key)")

    return _S3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )

# Optional: direct browser upload helper (keep commented until needed)
# def presign_put_url(filename: str, content_type: str = "application/octet-stream", expires_seconds: int = 600) -> tuple[str, str]:
#     key = f"{_PREFIX.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
#     url = _S3.generate_presigned_url(
#         "put_object",
#         Params={"Bucket": _BUCKET, "Key": key, "ContentType": content_type},
#         ExpiresIn=expires_seconds,
#     )
#     return url, f"s3://{_BUCKET}/{key}"

__all__ = ["put_bytes", "presign_get_url"]




