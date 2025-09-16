# src/backend/storage_s3.py
from __future__ import annotations
import os, uuid
import boto3
from botocore.client import Config

# Environment variables
bucket = os.environ.get("S3_BUCKET")
prefix = os.environ.get("S3_PREFIX", "uploads/")
region = os.environ.get("AWS_REGION", "us-east-1")

if not bucket:
    raise RuntimeError("S3_BUCKET is not set")

# S3 client
_s3 = boto3.client(
    "s3",
    region_name=region,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)

def put_bytes(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes to S3 and return the object key."""
    key = f"{prefix.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    _s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key

def presign_get_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned GET URL for an S3 object."""
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )

def presign_put_url(filename: str, content_type: str = "application/octet-stream", expires_in: int = 3600) -> tuple[str, str]:
    """Generate a presigned PUT URL for uploading a file directly to S3."""
    key = f"{prefix.rstrip('/')}/{uuid.uuid4().hex}-{filename}"
    url = _s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )
    return url, key



