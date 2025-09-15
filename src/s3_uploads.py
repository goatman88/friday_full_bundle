import time
import boto3
from botocore.client import Config
from .settings import AWS_REGION, S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

_session = boto3.session.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID or None,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY or None,
    region_name=AWS_REGION or None,
)
_s3 = _session.client("s3", config=Config(s3={"addressing_style": "virtual"}))

def create_multipart(key: str, content_type: str):
    resp = _s3.create_multipart_upload(
        Bucket=S3_BUCKET,
        Key=key,
        ContentType=content_type,
        ACL="private",
    )
    return resp["UploadId"]

def presign_part_urls(key: str, upload_id: str, part_numbers: list[int], expires=3600):
    urls = []
    for pn in part_numbers:
        url = _s3.generate_presigned_url(
            "upload_part",
            Params={"Bucket": S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": pn},
            ExpiresIn=expires,
        )
        urls.append({"partNumber": pn, "url": url})
    return urls

def complete_multipart(key: str, upload_id: str, parts: list[dict]):
    # parts = [{"ETag": "...", "PartNumber": 1}, ...] from client after uploads
    _s3.complete_multipart_upload(
        Bucket=S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )
    # Optionally return a signed GET to download
    get_url = _s3.generate_presigned_url("get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=3600)
    return {"ok": True, "key": key, "get_url": get_url, "ts": int(time.time())}



