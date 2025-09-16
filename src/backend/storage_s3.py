# src/backend/storage_s3.py
from __future__ import annotations
import os, uuid
import boto3
from botocore.client import Config

_BUCKET = os.getenv("S3_BUCKET")
_PREFIX = os.getenv("S3_PREFIX", "uploads/")
_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

_S3 = boto3.client(
    "s3",
    region_name=_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)

def _new_key(filename: str) -> str:
    return f"{_PREFIX.rstrip('/')}/{uuid.uuid4().hex}-{filename}"

def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """Server-side upload of bytes (useful for small files). Returns s3:// URI."""
    if not _BUCKET:
        raise RuntimeError("S3_BUCKET is not set")
    key = _new_key(filename)
    _S3.put_object(Bucket=_BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"s3://{_BUCKET}/{key}"

def presign_put_url(filename: str, content_type: str = "application/octet-stream", expires_seconds: int = 600) -> tuple[str, str]:
    """
    Create a presigned HTTPS PUT URL for direct browser upload.
    Returns (url, s3_uri).
    """
    if not _BUCKET:
        raise RuntimeError("S3_BUCKET is not set")
    key = _new_key(filename)
    url = _S3.generate_presigned_url(
        "put_object",
        Params={"Bucket": _BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_seconds,
    )
    return url, f"s3://{_BUCKET}/{key}"

def presign_get_url(s3_uri: str, expires_seconds: int = 600) -> str:
    """Create a presigned HTTPS GET URL from an s3://bucket/key URI."""
    if not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
        raise ValueError("presign_get_url expects 's3://bucket/key'")
    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    return _S3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )

__all__ = ["put_bytes", "presign_put_url", "presign_get_url"]








