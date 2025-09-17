# src/app.py
from __future__ import annotations

import os
import time
from typing import List, Optional, Dict

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr, conint

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
API_BASE = "/api"
RAG_BASE = f"{API_BASE}/rag"

AWS_BUCKET = os.environ.get("AWS_S3_BUCKET")  # REQUIRED
AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")  # optional (e.g., MinIO)

if not AWS_BUCKET:
    # We allow the process to start (so /api/health works), but any S3 call will raise.
    pass

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=AWS_ENDPOINT_URL or None,  # None = AWS normal
    # boto3 will pick up AWS creds from env/role automatically (Render supports env vars)
)

# -----------------------------------------------------------------------------
# Models (Pydantic v2 style)
# -----------------------------------------------------------------------------
class UploadUrlRequest(BaseModel):
    filename: constr(strip_whitespace=True, min_length=1)
    content_type: constr(strip_whitespace=True, min_length=1) = "application/octet-stream"


class UploadUrlResponse(BaseModel):
    put_url: str
    s3_uri: str


class ConfirmMetadata(BaseModel):
    collection: constr(strip_whitespace=True, min_length=1) = "default"
    tags: List[str] = Field(default_factory=list)
    source: constr(strip_whitespace=True, min_length=1) = "cli"


class Chunking(BaseModel):
    size: conint(gt=0) = 1200
    overlap: conint(ge=0) = 150


class ConfirmUploadRequest(BaseModel):
    s3_uri: constr(strip_whitespace=True, min_length=1)
    title: constr(strip_whitespace=True, min_length=1) = "Demo file"
    external_id: Optional[str] = None
    metadata: ConfirmMetadata = Field(default_factory=ConfirmMetadata)
    chunk: Chunking = Field(default_factory=Chunking)


class ConfirmUploadResponse(BaseModel):
    ok: bool = True
    indexed_at: float
    detail: Dict[str, str] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    q: constr(strip_whitespace=True, min_length=1)


class QueryResponse(BaseModel):
    ok: bool = True
    answers: List[str] = Field(default_factory=list)
    note: str = "Query endpoint is a placeholder. Implement your RAG search to return real answers."


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="Friday RAG Service", version="0.1.0")

# Permissive CORS so your local frontend can hit it easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def head_bucket_or_raise():
    if not AWS_BUCKET:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET is not set")
    try:
        s3.head_bucket(Bucket=AWS_BUCKET)
    except NoCredentialsError as e:
        raise HTTPException(status_code=500, detail=f"AWS credentials not found: {e}") from e
    except ClientError as e:
        # If bucket doesn't exist or no access, this will be 403/404
        code = int(getattr(e.response, "get", lambda *_: 500)("ResponseMetadata", {}).get("HTTPStatusCode", 500))
        raise HTTPException(status_code=code, detail=f"S3 head_bucket failed for {AWS_BUCKET}: {e}")


def make_presigned_put_url(key: str, content_type: str, expires_seconds: int = 900) -> str:
    params = {"Bucket": AWS_BUCKET, "Key": key}
    # The client must send Content-Type with the PUT if we include it in Conditions; for simplicity we don’t
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={**params, "ContentType": content_type},
        ExpiresIn=expires_seconds,
    )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get(f"{API_BASE}/health")
def api_health():
    return {"ok": True, "service": "rag", "region": AWS_REGION}


@app.get(f"{RAG_BASE}/health")
def rag_health():
    # Verify S3 connectivity and bucket access
    head_bucket_or_raise()
    return {"ok": True, "bucket": AWS_BUCKET, "region": AWS_REGION}


@app.post(f"{RAG_BASE}/upload_url", response_model=UploadUrlResponse)
def rag_upload_url(req: UploadUrlRequest):
    """
    Returns a presigned S3 PUT URL and the eventual s3:// URI where the file will live.
    Your client should PUT the bytes to put_url, then call /confirm_upload with the s3_uri.
    """
    head_bucket_or_raise()
    # Simple, unique-ish key under a prefix. Adjust to your liking.
    key = f"uploads/{int(time.time())}-{req.filename}"
    try:
        put_url = make_presigned_put_url(key, req.content_type)
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to create presigned URL: {e}") from e
    s3_uri = f"s3://{AWS_BUCKET}/{key}"
    return UploadUrlResponse(put_url=put_url, s3_uri=s3_uri)


@app.post(f"{RAG_BASE}/confirm_upload", response_model=ConfirmUploadResponse)
def rag_confirm_upload(req: ConfirmUploadRequest):
    """
    Stub indexer: in a real app, you would fetch the object from S3,
    chunk it (req.chunk), embed it, and write to your vector DB.
    We return 200 so your CLI sanity checks pass.
    """
    # Quick sanity of s3_uri format; skip strict validation so any s3-compatible URI passes.
    if not req.s3_uri.startswith("s3://"):
        raise HTTPException(status_code=400, detail="s3_uri must start with s3://")

    # Optionally ensure object exists:
    try:
        bucket, key = req.s3_uri.replace("s3://", "", 1).split("/", 1)
        s3.head_object(Bucket=bucket, Key=key)
    except Exception:
        # Don’t hard-fail; some setups use eventual consistency or different credentials.
        pass

    detail = {
        "title": req.title,
        "external_id": req.external_id or "",
        "collection": req.metadata.collection,
        "tags": ",".join(req.metadata.tags or []),
        "source": req.metadata.source,
        "chunk_size": str(req.chunk.size),
        "chunk_overlap": str(req.chunk.overlap),
        "s3_uri": req.s3_uri,
    }
    return ConfirmUploadResponse(ok=True, indexed_at=time.time(), detail=detail)


@app.post(f"{RAG_BASE}/query", response_model=QueryResponse)
def rag_query(req: QueryRequest):
    """
    Placeholder that keeps your probes green (returns 200).
    Swap this out to perform your real vector search.
    """
    # Return a deterministic dummy “answer”
    return QueryResponse(
        ok=True,
        answers=[f"(demo) You asked: {req.q} — plug in your RAG search here."],
    )





















































































