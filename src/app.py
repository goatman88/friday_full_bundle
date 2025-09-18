from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import os
import time
import hashlib
from dotenv import load_dotenv

from fastapi import FastAPI, Body, Path, HTTPException, Request
from pydantic import BaseModel, Field

# ---------- env ----------
load_dotenv()

# ---------- FastAPI ----------
app = FastAPI(title="Friday RAG API", version="0.1.1")

# ---------- simple text utils ----------
def _norm(s: str) -> List[str]:
    return [
        tok for tok in s.lower().replace("\n", " ").split()
        if tok.isascii() and any(c.isalnum() for c in tok)
    ]

def _split_into_chunks(text: str, size: int = 800, overlap: int = 120) -> List[str]:
    words = _norm(text)
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(len(words), start + size)
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks

# ---------- in-memory vector-ish index ----------
@dataclass
class Doc:
    id: str
    text: str
    source: str  # e.g., "faiss" or "s3"

class TinyIndex:
    """
    Super-light keyword index. No external deps.
    """
    def __init__(self) -> None:
        self.docs: List[Doc] = []
        self.inv: Dict[str, List[int]] = {}  # token -> list of doc indices

    def add(self, texts: List[str], source: str) -> int:
        added = 0
        for t in texts:
            doc = Doc(id=hashlib.sha1((t+source).encode()).hexdigest()[:12], text=t, source=source)
            self.docs.append(doc)
            idx = len(self.docs) - 1
            for tok in set(_norm(t)):
                self.inv.setdefault(tok, []).append(idx)
            added += 1
        return added

    def search(self, q: str, k: int = 5) -> List[Doc]:
        toks = set(_norm(q))
        if not toks:
            return []
        scores: Dict[int, int] = {}
        for tok in toks:
            for idx in self.inv.get(tok, []):
                scores[idx] = scores.get(idx, 0) + 1
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [self.docs[i] for i, _ in ranked]

# Two side-by-side indexes
faiss_like = TinyIndex()   # our local "FAISS" stand-in
s3_like    = TinyIndex()   # our S3-fed index

# ---------- upload scratch (token -> bytes) ----------
_upload_bin: Dict[str, bytes] = {}

def _new_token() -> str:
    return hashlib.sha1(f"{time.time_ns()}".encode()).hexdigest()[:16]

# ---------- models ----------
class UploadUrlResponse(BaseModel):
    token: str
    put_url: str

class ConfirmUploadBody(BaseModel):
    collection: str = Field(default="default")
    chunk_size: int = Field(default=1200, ge=100, le=4000)
    overlap: int = Field(default=150, ge=0, le=1000)
    index: str = Field(default="faiss", description="faiss|s3|both")

class QueryRequest(BaseModel):
    q: str
    top_k: int = Field(default=5, ge=1, le=25)
    index: str = Field(default="both", description="faiss|s3|both")

# ---------- routes ----------
@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}

@app.post("/api/rag/upload_url", response_model=UploadUrlResponse)
def get_upload_url() -> UploadUrlResponse:
    """
    For local dev we return a fake pre-signed PUT target under our own API.
    Client will PUT the bytes to /api/rag/upload_put/{token}.
    """
    token = _new_token()
    return UploadUrlResponse(token=token, put_url=f"/api/rag/upload_put/{token}")

@app.put("/api/rag/upload_put/{token}")
async def upload_put(token: str = Path(...), request: Request = None) -> Dict[str, Any]:
    data = await request.body()
    if not data:
        raise HTTPException(400, "Empty upload")
    _upload_bin[token] = bytes(data)
    return {"token": token, "bytes": len(data), "ok": True}

@app.put("/api/rag/confirm_upload")
def confirm_upload(body: ConfirmUploadBody = Body(...)) -> Dict[str, Any]:
    """
    Reads the uploaded bytes from the tokened PUT (already stored),
    chunks them, and inserts into the chosen index(es).
    """
    # To stay compatible with the previous dummy client, allow token in query too
    # but we’ll accept it via env or most recent token if only one exists.
    if not _upload_bin:
        raise HTTPException(400, "No uploaded payload found. Call upload_url -> upload_put first.")
    # Pick the most recent token
    token = list(_upload_bin.keys())[-1]
    raw = _upload_bin.pop(token).decode("utf-8", errors="ignore")
    chunks = _split_into_chunks(raw, size=body.chunk_size, overlap=body.overlap)
    if not chunks:
        return {"indexed": 0, "chunks": 0, "detail": "No usable text"}

    targets = []
    if body.index == "faiss":
        targets = [faiss_like]
    elif body.index == "s3":
        targets = [s3_like]
    else:
        targets = [faiss_like, s3_like]

    total = 0
    for t in targets:
        total += t.add(chunks, source="faiss" if t is faiss_like else "s3")

    return {"indexed": total, "chunks": len(chunks), "collection": body.collection, "index": body.index}

@app.post("/api/rag/query")
def query_rag(payload: QueryRequest = Body(...)) -> Dict[str, Any]:
    which = payload.index
    if which == "faiss":
        docs = faiss_like.search(payload.q, k=payload.top_k)
    elif which == "s3":
        docs = s3_like.search(payload.q, k=payload.top_k)
    else:
        # merge results from both
        a = faiss_like.search(payload.q, k=payload.top_k)
        b = s3_like.search(payload.q, k=payload.top_k)
        # naive merge preferring local hits first, then s3
        seen = set()
        docs = []
        for d in a + b:
            if d.id not in seen:
                docs.append(d); seen.add(d.id)
        docs = docs[:payload.top_k]

    if not docs:
        return {"answer": "No matches in index.", "hits": {}}

    return {
        "answer": docs[0].text[:240],
        "hits": {d.id: {"source": d.source, "preview": d.text[:200]} for d in docs}
    }

# Optional: a tiny root to prove the service lives at /
@app.get("/")
def root() -> Dict[str, Any]:
    return {"service": "friday", "docs": "/docs", "health": "/api/health"}






























































































