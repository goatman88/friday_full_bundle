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
    return f"s3://{_bucket}/{key}"

def presign_get_url(s3_uri: str, expires_seconds: int = 600) -> str:
    """s3_uri like 's3://bucket/key' -> presigned HTTPS URL"""
    if not s3_uri.startswith("s3://"):
        raise ValueError("Invalid s3_uri")
    _, rest = s3_uri.split("s3://", 1)
    bucket, key = rest.split("/", 1)
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )
