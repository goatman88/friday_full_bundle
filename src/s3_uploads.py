"""
S3 multipart uploads (presigned) + small direct uploads.

Env (required):
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET
Optional:
  S3_PREFIX            - e.g. "uploads/" (will be prefixed to object keys)
  MAX_DIRECT_MB        - max size for direct server upload (default 10)
"""

from __future__ import annotations
import os, time, typing as t, hashlib, hmac
from dataclasses import dataclass

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

S3_BUCKET = os.environ["S3_BUCKET"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_PREFIX = os.environ.get("S3_PREFIX", "").lstrip("/")

# Keep timeouts generous for large files and poor networks
_s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=BotoConfig(s3={"addressing_style": "virtual"}, retries={"max_attempts": 8, "mode": "standard"}),
)

def _key_for(filename: str, user_id: str | None = None) -> str:
    base = f"{int(time.time())}-{filename}"
    if user_id:
        base = f"{user_id}/{base}"
    return f"{S3_PREFIX}{base}" if S3_PREFIX else base

@dataclass
class MultipartStart:
    upload_id: str
    key: str

def initiate_multipart(filename: str, content_type: str, user_id: str | None = None) -> MultipartStart:
    key = _key_for(filename, user_id)
    try:
        resp = _s3.create_multipart_upload(Bucket=S3_BUCKET, Key=key, ContentType=content_type)
        return MultipartStart(upload_id=resp["UploadId"], key=key)
    except ClientError as e:
        raise RuntimeError(f"S3 initiate failed: {e.response.get('Error', {}).get('Message', str(e))}")

def sign_part(key: str, upload_id: str, part_number: int, expires_seconds: int = 3600) -> dict:
    # We return a presigned URL for PUTing the part body.
    try:
        url = _s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires_seconds,
            HttpMethod="PUT",
        )
        return {"url": url, "headers": {"Content-Type": "application/octet-stream"}}
    except ClientError as e:
        raise RuntimeError(f"S3 sign_part failed: {e.response.get('Error', {}).get('Message', str(e))}")

def complete_multipart(key: str, upload_id: str, parts: list[dict]) -> dict:
    """parts = [{ "ETag": "...", "PartNumber": 1 }, ...]"""
    try:
        _s3.complete_multipart_upload(
            Bucket=S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": sorted(parts, key=lambda p: p["PartNumber"])},
        )
        url = f"s3://{S3_BUCKET}/{key}"
        # Optionally include a public https URL if the bucket/object is public
        https_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
        return {"ok": True, "bucket": S3_BUCKET, "key": key, "s3_uri": url, "https_url": https_url}
    except ClientError as e:
        raise RuntimeError(f"S3 complete failed: {e.response.get('Error', {}).get('Message', str(e))}")

def abort_multipart(key: str, upload_id: str) -> dict:
    try:
        _s3.abort_multipart_upload(Bucket=S3_BUCKET, Key=key, UploadId=upload_id)
        return {"ok": True}
    except ClientError as e:
        raise RuntimeError(f"S3 abort failed: {e.response.get('Error', {}).get('Message', str(e))}")

# Small direct upload (server receives file then puts to S3).
_MAX_DIRECT_MB = int(os.environ.get("MAX_DIRECT_MB", "10"))

def put_object_direct(filename: str, stream, content_type: str, user_id: str | None = None) -> dict:
    key = _key_for(filename, user_id)
    try:
        _s3.upload_fileobj(
            Fileobj=stream,
            Bucket=S3_BUCKET,
            Key=key,
            ExtraArgs={"ContentType": content_type},
            Config=boto3.s3.transfer.TransferConfig(max_concurrency=4, multipart_threshold=8*1024*1024),
        )
        return {"ok": True, "bucket": S3_BUCKET, "key": key, "https_url": f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"}
    except ClientError as e:
        raise RuntimeError(f"S3 put_object failed: {e.response.get('Error', {}).get('Message', str(e))}")

