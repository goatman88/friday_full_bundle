from __future__ import annotations
from fastapi import FastAPI, APIRouter, Body, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import time
import uuid

app = FastAPI(
    title="Friday RAG API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS (open by default; tighten if you need)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# In-memory "storage" + "index"
# -----------------------------
# mem://uploads/<token> -> bytes
UPLOADS: Dict[str, bytes] = {}
# indexed docs: token -> {"text": str, "meta": dict}
INDEX: Dict[str, Dict] = {}

# -----------------------------
# Models
# -----------------------------
class UploadUrlRequest(BaseModel):
    file_name: str = Field(..., description="Client-side file name (any string)")
    content_type: str = Field("text/plain", description="MIME type of content")

class UploadUrlResponse(BaseModel):
    put_url: str
    s3_uri: str
    expire_sec: int = 900
    note: str = "This is a local in-memory PUT URL, not real S3."

class ChunkConfig(BaseModel):
    size: int = 1200
    overlap: int = 150

class ConfirmUploadRequest(BaseModel):
    s3_uri: str
    title: str = "demo file"
    external_id: str = "demo_1"
    metadata: Dict[str, object] = Field(default_factory=dict)
    chunk: ChunkConfig = Field(default_factory=ChunkConfig)
    source: str = "cli"

class ConfirmUploadResponse(BaseModel):
    ok: bool
    indexed_count: int
    indexed_ids: List[str]

class RagQueryRequest(BaseModel):
    q: str
    top_k: int = 3

class RagQueryAnswer(BaseModel):
    answer: str
    hits: List[Dict[str, object]]

# -----------------------------
# Root & health
# -----------------------------
@app.get("/", response_class=PlainTextResponse)
def root() -> str:
    return "Friday RAG API is up. See /docs"

def _health_payload() -> Dict[str, object]:
    return {"status": "ok", "ts": int(time.time()), "indexed": len(INDEX)}

@app.get("/health")
def health_root():
    return _health_payload()

# For your PowerShell that uses /api/health
api = APIRouter(prefix="/api")

@api.get("/health")
def health_api():
    return _health_payload()

# -----------------------------
# RAG routes
# -----------------------------
rag = APIRouter(prefix="/rag", tags=["rag"])

@rag.post("/upload_url", response_model=UploadUrlResponse)
def get_upload_url(req: UploadUrlRequest):
    """
    Returns a *local* PUT URL (this app), so you can do a simple HTTP PUT with your bytes.
    No AWS creds required. We store bytes in memory under a token.
    """
    token = uuid.uuid4().hex
    put_url = f"/api/rag/upload_put/{token}"
    s3_uri = f"mem://uploads/{token}"
    return UploadUrlResponse(put_url=put_url, s3_uri=s3_uri)

@rag.put("/upload_put/{token}")
async def put_upload(token: str, request: Request, content_type: Optional[str] = None):
    """
    Accept raw bytes and store in memory keyed by token.
    Returns size stored.
    """
    body = await request.body()
    UPLOADS[token] = body
    return {"stored": len(body), "token": token}

@rag.post("/confirm_upload", response_model=ConfirmUploadResponse)
def confirm_upload(req: ConfirmUploadRequest):
    """
    Take the mem://uploads/<token> s3_uri, move into the 'index' (very naive).
    """
    prefix = "mem://uploads/"
    if not req.s3_uri.startswith(prefix):
        raise HTTPException(status_code=400, detail="s3_uri must be mem://uploads/<token> from /rag/upload_url")
    token = req.s3_uri[len(prefix):]
    data = UPLOADS.get(token)
    if data is None:
        raise HTTPException(status_code=404, detail="No uploaded data for token")

    text = ""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = f"<{len(data)} bytes>"

    INDEX[token] = {
        "text": text,
        "meta": {
            "title": req.title,
            "external_id": req.external_id,
            "source": req.source,
            **req.metadata,
        },
    }
    return ConfirmUploadResponse(ok=True, indexed_count=len(INDEX), indexed_ids=[token])

@rag.post("/query", response_model=RagQueryAnswer)
def rag_query(req: RagQueryRequest):
    """
    Ultra-simple retrieval: return lines containing the query substring (case-insensitive).
    """
    q = req.q.strip().lower()
    hits: List[Dict[str, object]] = []
    for token, rec in INDEX.items():
        text: str = rec["text"]
        if q and q in text.lower():
            snippet = text
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            hits.append({
                "token": token,
                "snippet": snippet,
                "meta": rec["meta"],
            })
            if len(hits) >= req.top_k:
                break

    answer = "No matches in index." if not hits else f"Found {len(hits)} possible match(es)."
    return RagQueryAnswer(answer=answer, hits=hits)

# mount routers
api.include_router(rag)
app.include_router(api)






















































































