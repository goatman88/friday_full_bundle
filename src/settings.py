import os

# --- Core configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")  # 1536 dims
EMBED_DIM = int(os.environ.get("EMBED_DIM", "1536"))

DATABASE_URL = os.environ.get("DATABASE_URL", "")  # e.g., postgres://...render.com/...
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")  # gate /admin & db-admin endpoints

# S3 (kept for your existing endpoints in s3_uploads.py)
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_REGION = os.environ.get("S3_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# CORS: not needed when same origin; set to "*" only if you host a separate FE
FRIDAY_FRONTEND_ORIGIN = os.environ.get("FRIDAY_FRONTEND_ORIGIN", "")

