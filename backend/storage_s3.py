# backend/storage_s3.py
from __future__ import annotations
import os, uuid
import boto3

_bucket = os.environ.get("S3_BUCKET")
_prefix = os.environ.get("S3_PREFIX", "uploads/")
_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

if not _bucket:
    raise RuntimeError("S3_BUCKET is not set")

_s3 = boto3.client("s3", region_name=_region)

def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    key = f"{_prefix.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    _s3.put_object(Bucket=_bucket, Key=key, Body=data, ContentType=content_type)
    # Return a public-style URL if bucket is public; otherwise return s3:// and handle access as you prefer
    return f"s3://{_bucket}/{key}"
