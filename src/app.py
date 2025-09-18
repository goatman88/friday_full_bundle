# src/app.py
from fastapi import FastAPI
from fastapi import Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import os

# Load .env at startup (fixes "ModuleNotFoundError: dotenv")
load_dotenv()

app = FastAPI(title="Friday RAG API", version="0.1.0")

# ---------- Models ----------
class QueryRequest(BaseModel):
    q: str
    top_k: int = 5


# ---------- Helpers (minimal stubs so everything stays up) ----------
def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload

def _stub_answer(q: str) -> Dict[str, Any]:
    # This is where you’ll plug real FAISS/S3 logic later.
    # For now we return a deterministic stub that your client already expects.
    return {"answer": "No matches in index.", "hits": {}}


# ---------- Default/Health ----------
@app.get("/")
def root() -> Dict[str, str]:
    return {"service": "friday", "status": "ok"}

@app.get("/api/health")
def health() -> Dict[str, str]:
    # Add lightweight checks here later if you want (S3 creds, etc.)
    return {"status": "ok"}


# ---------- Legacy RAG routes (kept for your PowerShell client) ----------
# NOTE: These just return safe stubs so calls don’t 404.
@app.post("/api/rag/upload_url")
def rag_upload_url() -> Dict[str, Any]:
    # In a real system you’d mint a pre-signed S3 URL here.
    return _ok({"upload_url": "stub://upload", "token": "stub-token"})

@app.put("/api/rag/upload_put/{token}")
def rag_upload_put(token: str) -> Dict[str, Any]:
    return _ok({"ok": True, "token": token})

@app.post("/api/rag/confirm_upload")
def rag_confirm_upload(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    # payload would normally include where the files landed, collection, etc.
    return _ok({"indexed": 0, "detail": "stub confirm complete"})

@app.post("/api/rag/query")
def rag_query(req: QueryRequest) -> Dict[str, Any]:
    # Keep this route because your PS script calls it.
    return _stub_answer(req.q)


# ---------- Side-by-side indexes ----------
# FAISS
@app.post("/api/rag/faiss/query")
def faiss_query(req: QueryRequest) -> Dict[str, Any]:
    return _stub_answer(req.q)

# S3-backed (vector store you’ll add later)
@app.post("/api/rag/s3/query")
def s3_query(req: QueryRequest) -> Dict[str, Any]:
    return _stub_answer(req.q)





























































































