import os

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")]
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "512"))

# Basic guards
if not ADMIN_TOKEN:
    print("[WARN] ADMIN_TOKEN not set — /admin endpoints will reject requests.")
if not (S3_BUCKET and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
    print("[WARN] S3 env vars incomplete — uploads will be disabled.")

