# Placeholder S3 ingest helpers. Real version will:
# - create a presigned upload URL
# - stream to storage
# - trigger indexing job
def create_presigned_url_stub() -> str:
    return "/api/rag/upload_url"
