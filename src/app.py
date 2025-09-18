# src/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

api = FastAPI(title="Friday RAG API", version="0.1.0")

# CORS (adjust origins as needed)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/health")
async def health():
    return {"status": "ok"}

# -------- Optional stubs you can fill later ----------
from typing import List, Optional

class ConfirmUploadRequest(BaseModel):
    s3: str
    collection: str = "default"
    chunk_size: int = 1200
    overlap: int = 150
    source: str = "cli"

@api.post("/rag/confirm_upload")
async def confirm_upload(req: ConfirmUploadRequest):
    # TODO: index your uploaded file(s)
    return {"ok": True, "indexed": 0}

class QueryRequest(BaseModel):
    q: str
    top_k: int = 5

@api.post("/rag/query")
async def query(req: QueryRequest):
    # TODO: answer from your index
    return {"answer": "No matches in index.", "hits": []}

























































































