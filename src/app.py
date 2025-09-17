# src/app.py
from __future__ import annotations

import os
import time
import typing as t
from uuid import uuid4

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ------- Optional S3 presign support -------
# If AWS creds/role and S3_BUCKET are present, we'll generate real presigned URLs.
# Otherwise we return a fake URL so the rest of the flow can be exercised.
USE_S3 = False
_s3 = None
_bucket = os.getenv("S3_BUCKET")

try:
    import boto3  # type: ignore

    if _bucket:
        _s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))
        USE_S3 = True
except Exception:
    # boto3 not available or not configured – we'll fall back to fake URLs
    USE_S3 = False

# ------- App setup -------
app = FastAPI(title="Friday RAG API", version="0.1.0")

# permissive CORS so your local pages and PowerShell can hit it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory "index" to prove confirm/query are wired
INDEX: list[dict[str, t.Any]] = []

# ------- Schemas -------
class UploadUrlReq(BaseModel):
    filename: str = Field(..., example="demo.txt")
    content_type: str = Field(..., example="text/plain")


class UploadUrlResp(BaseModel):
    put_url: str
    s3_uri: str
    get_url: t.Optional[str] = None
    # free to include any extra fields your client prints


class ChunkCfg(BaseModel):
    size: int = Field(1200, ge=1)
    overlap: int = Field(150, ge=0)


class ConfirmReq(BaseModel):
    s3_uri: str
    title: str
    external_id: str
    metadata: dict[str, t.Any] = Field(default_factory=dict)
    chunk: ChunkCfg = Field(default_factory=ChunkCfg)


class ConfirmResp(BaseModel):
    indexed: bool = True
    id: str
    received: ConfirmReq


class QueryReq(BaseModel):
    q: str


class QueryResp(BaseModel):
    query: str
    hits: list[dict[str, t.Any]]


# ------- Core routes (mounted twice: with and without /api) -------
rag = APIRouter()


@rag.post("/upload_url", response_model=UploadUrlResp)
def upload_url(req: UploadUrlReq) -> UploadUrlResp:
    """
    Step 1: ask backend for a pre-signed PUT URL.
    If S3 is configured we return a real presigned URL.
    Otherwise we return a fake URL so the client can keep going.
    """
    key = f"uploads/{int(time.time())}-{uuid4().hex}-{req.filename}"

    if USE_S3 and _s3 and _bucket:
        try:
            put_url = _s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": _bucket, "Key": key, "ContentType": req.content_type},
                ExpiresIn=int(os.getenv("PRESIGN_TTL", "900")),
            )
            get_url = _s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": _bucket, "Key": key},
                ExpiresIn=int(os.getenv("PRESIGN_TTL", "900")),
            )
            s3_uri = f"s3://{_bucket}/{key}"
            return UploadUrlResp(put_url=put_url, s3_uri=s3_uri, get_url=get_url)
        except Exception as e:
            # If your AWS role/creds are wrong, surface it clearly
            raise HTTPException(status_code=500, detail=f"S3 presign failed: {e}")

    # Fallback (no S3): return deterministic, fake endpoints so your PS script won't crash.
    fake_base = os.getenv("FAKE_STORAGE_BASE", "https://example.invalid/dev-bucket")
    put_url = f"{fake_base}/{key}?method=PUT"
    s3_uri = f"s3://dev-bucket/{key}"
    get_url = f"{fake_base}/{key}?method=GET"
    return UploadUrlResp(put_url=put_url, s3_uri=s3_uri, get_url=get_url)


@rag.post("/confirm_upload", response_model=ConfirmResp)
def confirm_upload(req: ConfirmReq) -> ConfirmResp:
    """
    Step 4: tell backend to index the uploaded object.
    We just stash it in memory to prove the round-trip works.
    Replace this with your real chunking/embedding/indexing.
    """
    doc_id = uuid4().hex
    INDEX.append({"id": doc_id, "doc": req.model_dump()})
    return ConfirmResp(id=doc_id, received=req)


@rag.post("/query", response_model=QueryResp)
def query(req: QueryReq) -> QueryResp:
    """
    Optional: tiny demo query endpoint.
    It 'matches' docs whose title or external_id contains any token from q.
    """
    tokens = {tok.lower() for tok in req.q.split()}
    hits: list[dict[str, t.Any]] = []
    for row in INDEX:
        d = row["doc"]
        title = str(d.get("title", "")).lower()
        ext = str(d.get("external_id", "")).lower()
        if any(tok in title or tok in ext for tok in tokens):
            hits.append({"id": row["id"], "title": d.get("title"), "external_id": d.get("external_id"), "s3_uri": d.get("s3_uri")})
    return QueryResp(query=req.q, hits=hits)


# Health (both with and without /api)
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "ts": int(time.time()), "indexed": len(INDEX)}


# Mount the RAG router at two prefixes so your client can try either one.
app.include_router(rag, prefix="/rag", tags=["rag"])
app.include_router(rag, prefix="/api/rag", tags=["rag (api)"])

# Convenience root (optional): helps avoid 404 on GET /
@app.get("/")
def root():
    return {
        "message": "Friday RAG backend is alive",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "endpoints": ["/api/health", "/api/rag/upload_url", "/api/rag/confirm_upload", "/api/rag/query"],
    }






















































































