import boto3
import os
from botocore.client import Config

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    config=Config(signature_version="s3v4")
)

BUCKET = os.environ.get("S3_BUCKET")

def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Upload raw bytes to S3."""
    s3.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"s3://{BUCKET}/{key}"

def presign_get_url(key: str, expires_in: int = 3600):
    """Generate a presigned URL to download an object."""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires_in
    )

def presign_put_url(key: str, content_type: str = "application/octet-stream", expires_in: int = 3600):
    """Generate a presigned URL to upload an object directly from client."""
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in
    )
