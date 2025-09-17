# src/rag_api.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class ChunkCfg(BaseModel):
    size: int = 1200
    overlap: int = 150

class ConfirmReq(BaseModel):
    s3_uri: str
    title: str
    external_id: str
    metadata: Dict[str, Any] = {}
    chunk: ChunkCfg = ChunkCfg()

@router.get("/health")
def health():
    return {"ok": True}

@router.post("/upload_url")
def upload_url(filename: str, content_type: str):
    # TODO: return your real presigned URLs
    return {
        "put_url": "https://example.com/put",
        "s3_uri":  "s3://your-bucket/path/file",
    }

@router.post("/confirm_upload")
def confirm_upload(body: ConfirmReq):
    # TODO: kick off your indexing job here
    return {"ok": True, "indexed": {"external_id": body.external_id, "title": body.title}}
