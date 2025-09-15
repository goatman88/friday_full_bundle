"""
Lightweight S3 helper. This module must be importable at startup
to avoid 'No module named s3_uploads'.

Set env vars on Render:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION (default: us-east-1)
- S3_BUCKET
"""

import os
import boto3
from botocore.config import Config


def get_s3_client():
    # ultra conservative retries and timeouts
    cfg = Config(
        retries={"max_attempts": 5, "mode": "standard"},
        connect_timeout=5,
        read_timeout=120,
    )
    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        config=cfg,
    )


def bucket_name() -> str:
    b = os.environ.get("S3_BUCKET", "").strip()
    if not b:
        raise RuntimeError("S3_BUCKET env var is not set")
    return b


