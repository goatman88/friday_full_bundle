# src/app.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Storage locations (Render has a persistent /data mount) ---
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
if not DATA_DIR.exists():
    DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

VECTORIZER_PATH = DATA_DIR / "vectorizer.json"
MATRIX_PATH = DATA_DIR / "matrix.npy"
DOCS_PATH = DATA_DIR / "docs.json"

# --- Light RAG stack: TF-IDF + cosine similarity ---
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ---------- Models ----------
class Doc(BaseModel):
    id: str = Field(..., description="Your ID for this chunk/document")
    text: str = Field(..., description="Plain text content")


class ConfirmUploadRequest(BaseModel):
    # For Path B we accept raw texts directly. (You can add S3 later.)
    documents: List[Doc] = Field(..., description="List of docs/chunks to index")
    # Optional: when true we replace the whole index; else we append
    replace: bool = Field(default=True)


class QueryRequest(BaseModel):
    q: str = Field(..., description="User query")
    top_k: int = Field(default=5, ge=1, le=50)


class HealthResponse(BaseModel):
    status: str
    indexed: int = 0


# ---------- App ----------
API_ROOT = os.getenv("APP_ROOT", "/api").rstrip("/")
app = FastAPI(title="Friday RAG API", openapi_url=f"{API_ROOT}/openapi.json", docs_url="/docs")

# Allow everything for now; tighten later if you want
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------
def _save_index(vectorizer: TfidfVectorizer, matrix: np.ndarray, docs: List[Dict[str, Any]]) -> None:
    # Persist vectorizer as plain dict so we avoid pickle on Render
    vec_state = {
        "vocabulary_": vectorizer.vocabulary_,
        "idf_": vectorizer.idf_.tolist(),
        "stop_words_": list(vectorizer.stop_words_) if vectorizer.stop_words_ is not None else None,
        "ngram_range": vectorizer.ngram_range,
        "lowercase": vectorizer.lowercase,
        "norm": vectorizer.norm,
        "use_idf": vectorizer.use_idf,
        "smooth_idf": vectorizer.smooth_idf,
        "sublinear_tf": vectorizer.sublinear_tf,
    }
    VECTORIZER_PATH.write_text(json.dumps(vec_state))
    np.save(MATRIX_PATH, matrix)
    DOCS_PATH.write_text(json.dumps(docs))


def _load_index() -> tuple[TfidfVectorizer | None, np.ndarray | None, List[Dict[str, Any]]]:
    if not (VECTORIZER_PATH.exists() and MATRIX_PATH.exists() and DOCS_PATH.exists()):
        return None, None, []
    vec_state = json.loads(VECTORIZER_PATH.read_text())
    vectorizer = TfidfVectorizer(
        ngram_range=tuple(vec_state.get("ngram_range", (1, 1))),
        lowercase=bool(vec_state.get("lowercase", True)),
        norm=vec_state.get("norm", "l2"),
        use_idf=bool(vec_state.get("use_idf", True)),
        smooth_idf=bool(vec_state.get("smooth_idf", True)),
        sublinear_tf=bool(vec_state.get("sublinear_tf", False)),
    )
    # Rehydrate learned params
    vectorizer.vocabulary_ = {k: int(v) for k, v in vec_state["vocabulary_"].items()}
    vectorizer.idf_ = np.asarray(vec_state["idf_"])
    # stop_words_ can be None; if list, set as a set for sklearn
    sw = vec_state.get("stop_words_")
    vectorizer.stop_words_ = set(sw) if sw is not None else None

    matrix = np.load(MATRIX_PATH)
    docs = json.loads(DOCS_PATH.read_text())
    return vectorizer, matrix, docs


def _build_or_append_index(new_docs: List[Doc], replace: bool) -> int:
    """
    Build a brand new TF-IDF index (replace=True) or append to existing index (replace=False).
    Returns total doc count after operation.
    """
    new_docs_clean = [d for d in new_docs if d.text.strip()]

    if replace:
        texts = [d.text for d in new_docs_clean]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        matrix = vectorizer.fit_transform(texts)
        docs = [d.model_dump() for d in new_docs_clean]
        _save_index(vectorizer, matrix, docs)
        return len(docs)

    # Append mode: load then refit on combined corpus (simple & robust)
    old_vec, old_mat, old_docs = _load_index()
    if old_vec is None:
        return _build_or_append_index(new_docs, replace=True)

    texts = [d["text"] for d in old_docs] + [d.text for d in new_docs_clean]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    docs = old_docs + [d.model_dump() for d in new_docs_clean]
    _save_index(vectorizer, matrix, docs)
    return len(docs)


def _search(q: str, top_k: int) -> Dict[str, Any]:
    vectorizer, matrix, docs = _load_index()
    if vectorizer is None or matrix is None or not docs:
        return {"answer": "No matches in index.", "hits": []}

    q_vec = vectorizer.transform([q])
    sims = cosine_similarity(q_vec, matrix)[0]  # shape (N,)
    if sims.size == 0:
        return {"answer": "No matches in index.", "hits": []}

    idxs = np.argsort(-sims)[:top_k]
    hits = []
    for i in idxs:
        hit = {
            "id": docs[int(i)]["id"],
            "score": float(sims[int(i)]),
            "text": docs[int(i)]["text"],
        }
        hits.append(hit)

    # Very simple “answer”: return the best chunk (keep stubby — LLM comes later)
    answer = hits[0]["text"] if hits else "No matches in index."
    return {"answer": answer, "hits": hits}


# ---------- Routes (all under /api) ----------
@app.get(f"{API_ROOT}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    _, _, docs = _load_index()
    return HealthResponse(status="ok", indexed=len(docs))


@app.post(f"{API_ROOT}/rag/confirm_upload")
def confirm_upload(payload: ConfirmUploadRequest = Body(...)) -> Dict[str, Any]:
    total = _build_or_append_index(payload.documents, replace=payload.replace)
    return {"status": "ok", "indexed": total}


@app.post(f"{API_ROOT}/rag/query")
def query(payload: QueryRequest = Body(...)) -> Dict[str, Any]:
    return _search(payload.q, payload.top_k)


# Optional: root for sanity (kept outside /api for Render’s HEAD check)
@app.get("/")
def root():
    return {"service": "friday", "docs": "/docs", "api": API_ROOT}




























































































