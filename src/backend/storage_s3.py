# src/backend/storage_s3.py
from __future__ import annotations
import os, uuid
import boto3
from botocore.client import Config

_bucket = os.environ.get("S3_BUCKET")
_prefix = os.environ.get("S3_PREFIX", "uploads/")
_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

if not _bucket:
    raise RuntimeError("S3_BUCKET is not set")

_s3 = boto3.client(
    "s3",
    region_name=_region,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)

def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    key = f"{_prefix.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    _s3.put_object(Bucket=_bucket, Key=key, Body=data, ContentType=content_type)
    # return pointer used by rag_blueprint meta
    return f"s3://{_bucket}/{key}"

def presign_get_url(s3_uri: str, expires_seconds: int = 600) -> str:
    if not s3_uri.startswith("s3://"):
        raise ValueError("Invalid s3_uri (expected s3://bucket/key)")
    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )

