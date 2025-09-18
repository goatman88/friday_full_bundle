# src/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Friday RAG API", version="0.1.0")

# CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Health ----
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# ---- RAG stubs (safe placeholders; wire your real code later) ----
class ConfirmUploadRequest(BaseModel):
    s3: str
    collection: str = "default"
    chunk_size: int = 1200
    overlap: int = 150
    source: str = "cli"

@app.post("/api/rag/confirm_upload")
async def confirm_upload(req: ConfirmUploadRequest):
    # TODO: index your uploaded file(s)
    return {"ok": True, "indexed": 0}

class QueryRequest(BaseModel):
    q: str
    top_k: int = 5

@app.post("/api/rag/query")
async def query(req: QueryRequest):
    # TODO: answer from your index
    return {"answer": "No matches in index.", "hits": []}


























































































