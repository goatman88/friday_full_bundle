# src/app.py
from __future__ import annotations

import os
import json
from datetime import timedelta
from typing import Any, Dict

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Simple in-memory "presign" stub (replace with real S3 presign if you want) ---

class PresignReq(BaseModel):
    filename: str = Field(..., examples=["demo.txt"])
    content_type: str = Field(..., examples=["text/plain"])

class PresignResp(BaseModel):
    put_url: str
    s3_uri: str

class ConfirmChunkCfg(BaseModel):
    size: int = 1200
    overlap: int = 150

class ConfirmMeta(BaseModel):
    collection: str = "default"
    tags: list[str] = []
    source: str = "cli"

class ConfirmReq(BaseModel):
    s3_uri: str
    title: str = "Demo file"
    external_id: str = "demo_1"
    metadata: ConfirmMeta = ConfirmMeta()
    chunk: ConfirmChunkCfg = ConfirmChunkCfg()

class QueryReq(BaseModel):
    q: str

def _service_base() -> str:
    """
    Returns the public Render URL from env if you set one.
    Only used to fabricate demo presign URLs.
    """
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

def make_demo_presign(req: PresignReq) -> PresignResp:
    base = _service_base() or "https://example.invalid"
    # In a real implementation you’d call boto3 to create a presigned PUT.
    # Here we just return something that looks like a URL so your client can continue.
    put_url = f"{base}/fake-s3/{req.filename}?signature=demo&expires={int(timedelta(minutes=10).total_seconds())}"
    s3_uri = f"s3://fake-bucket/uploads/{req.filename}"
    return PresignResp(put_url=put_url, s3_uri=s3_uri)

# --- FastAPI app and routers ---

app = FastAPI(title="Friday RAG Demo", version="0.1.0")

# CORS (relaxed while testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

root = APIRouter()
rag = APIRouter()

@root.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}

@rag.post("/upload_url", response_model=PresignResp)
def upload_url(req: PresignReq) -> PresignResp:
    return make_demo_presign(req)

@rag.post("/confirm_upload")
def confirm_upload(req: ConfirmReq) -> Dict[str, Any]:
    # In production you’d enqueue indexing work here.
    return {
        "indexed": True,
        "received": json.loads(req.model_dump_json()),
    }

@rag.post("/query")
def query(req: QueryReq) -> Dict[str, Any]:
    # Stubbed answer so your CLI step 5 doesn’t 404
    return {
        "q": req.q,
        "answer": "This is a demo answer. The real RAG pipeline isn’t wired yet.",
        "chunks_considered": 0,
    }

# Mount routes at BOTH /api and / (so your scripts & probes succeed either way)
app.include_router(root, prefix="")
app.include_router(root, prefix="/api")

# RAG endpoints are available at:
#   /rag/*           and   /api/rag/*
app.include_router(rag, prefix="/rag")
app.include_router(rag, prefix="/api/rag")

# Optional: print routes at startup (helps when reading Render logs)
@app.on_event("startup")
async def _log_routes() -> None:
    paths = sorted({f"{r.methods} {r.path}" for r in app.router.routes})
    print("=== Mounted routes ===")
    for p in paths:
        print(p)





















































































