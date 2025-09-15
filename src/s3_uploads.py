"""
Minimal placeholder so `from src import s3_uploads` doesn't fail.
We'll wire multipart S3 uploads here after deploy is green.
"""
def not_ready():
    return {"ok": False, "reason": "S3 not wired yet"}


