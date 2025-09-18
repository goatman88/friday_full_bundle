# src/app.py
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---- App ----
app = FastAPI(
    title="Friday RAG API",
    version="0.1.0",
    openapi_url="/openapi.json",
)

# CORS (wide open for now; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Everything under /api
api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> Dict[str, Any]:
    """Simple health endpoint used by your PowerShell client."""
    return {
        "status": "ok",
        "ts": int(datetime.now(timezone.utc).timestamp()),
        "indexed": 0,
    }


# ---------- RAG stubs (keep simple & predictable) ----------
class UploadUrlResponse(BaseModel):
    token: str
    upload_url: str


class ConfirmUploadBody(BaseModel):
    s3: Optional[str] = None
    filename: Optional[str] = None
    collection: Optional[str] = "default"
    chunk_size: Optional[int] = 1200
    overlap: Optional[int] = 150
    source: Optional[str] = "cli"


class QueryBody(BaseModel):
    q: str
    top_k: Optional[int] = 5
    collection: Optional[str] = "default"


@api.post("/rag/upload_url", response_model=UploadUrlResponse)
def get_upload_url() -> UploadUrlResponse:
    return UploadUrlResponse(
        token="demo-token",
        upload_url="https://example.com/presigned-put-url",
    )


@api.put("/rag/upload_put/{token}")
def upload_put(token: str):
    if token != "demo-token":
        raise HTTPException(status_code=400, detail="Invalid token")
    return {"ok": True, "token": token}


@api.post("/rag/confirm_upload")
def confirm_upload(body: ConfirmUploadBody):
    return {"ok": True, "indexed": 0, "collection": body.collection}


@api.post("/rag/query")
def rag_query(body: QueryBody) -> Dict[str, Any]:
    return {"answer": "No matches in index.", "hits": []}  # type: ignore[reportUnknownArgumentType]


# ---------- Root helpers ----------
@api.get("/")
def api_root() -> Dict[str, Any]:
    return {"ok": True, "routes": ["/api/health", "/api/rag/*"]}


app.include_router(api)


@app.get("/")
def root():
    return {"hello": "world", "docs": "/docs", "api": "/api"}
























































































