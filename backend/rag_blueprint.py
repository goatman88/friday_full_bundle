# backend/rag_blueprint.py
from __future__ import annotations
import os, re, math, time, json
from typing import List, Optional, Dict, Any, Tuple
from flask import Blueprint, request, jsonify
from pydantic import BaseModel, Field
import requests

from openai import OpenAI
from backend.db import fetchone, fetchall, execute

# add to imports at the top:
import mimetypes
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document
from backend.storage_s3 import put_bytes

ALLOWED_EXTS = {".pdf", ".docx", ".txt"}

def _ext(name: str) -> str:
    name = name or ""
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""

def _read_pdf_bytes(b: bytes) -> str:
    # pdfminer needs a path or a bytes-like object; easiest is to pass bytes via a temp file.
    # To avoid temp files in Render ephemeral FS, pdfminer supports file-like objects, but a temp file is simplest.
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(b)
        tmp.flush()
        path = tmp.name
    try:
        txt = pdf_extract_text(path) or ""
        return _clean_text(txt)
    finally:
        try: _os.remove(path)
        except Exception: pass

def _read_docx_bytes(b: bytes) -> str:
    import io
    f = io.BytesIO(b)
    doc = Document(f)
    return _clean_text("\n".join(p.text for p in doc.paragraphs))

@bp.route("/index_file", methods=["POST"])
def index_file_route():
    """
    multipart/form-data:
      file: (required) pdf/docx/txt
      title: optional
      external_id: optional (we'll upsert by this if given)
      meta: optional JSON string
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field"}), 400

    up = request.files["file"]
    filename = secure_filename(up.filename or "upload.bin")
    ext = _ext(filename)
    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    raw = up.read()
    if not raw:
        return jsonify({"error": "Empty file"}), 400

    # store in S3
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    s3_uri = put_bytes(raw, filename, content_type=ctype)

    # parse text
    if ext == ".pdf":
        text = _read_pdf_bytes(raw)
        source = "pdf"
    elif ext == ".docx":
        text = _read_docx_bytes(raw)
        source = "docx"
    else:
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        text = _clean_text(text)
        source = "txt"

    if not text:
        return jsonify({"error": "No extractable text"}), 400

    # optional metadata/title/external_id
    title = request.form.get("title") or filename
    external_id = request.form.get("external_id") or None
    meta_str = request.form.get("meta") or "{}"
    try:
        meta = json.loads(meta_str)
    except Exception:
        meta = {}

    # preserve S3 URI in meta
    meta = dict(meta or {})
    meta["s3_uri"] = s3_uri
    meta["filename"] = filename
    meta["content_type"] = ctype

    # chunk + embed + insert
    chunks = _chunk_text(text)
    if not chunks:
        return jsonify({"error": "No indexable text after parsing"}), 400

    if external_id:
        doc_id = _upsert_doc_by_external_id(title, source, meta, external_id)
    else:
        doc_id = _insert_document(title, source, meta, None)

    embeds = _embed_texts(chunks)
    _insert_chunks(doc_id, chunks, embeds)

    return jsonify({
        "ok": True,
        "document_id": doc_id,
        "title": title,
        "source": source,
        "s3_uri": s3_uri,
        "chunks_indexed": len(chunks),
        "dims": EMBEDDING_DIMS,
        "model": EMBEDDING_MODEL
    })

bp = Blueprint("rag", __name__, url_prefix="/api/rag")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMS = 3072 if "large" in EMBEDDING_MODEL else 1536

oai = OpenAI(api_key=OPENAI_API_KEY)

# ------------------------------
# Utilities
# ------------------------------
def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s

def _chunk_text(text: str, max_tokens: int = 700, overlap: int = 120) -> List[str]:
    """
    Simple conservative splitter by approx tokens (assume ~4 chars/token).
    For higher quality, replace with a tiktoken-based splitter later.
    """
    text = _clean_text(text)
    if not text:
        return []

    max_chars = max_tokens * 4
    ov_chars = overlap * 4
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        # try to cut at sentence end
        window = text[start:end]
        cut = window.rfind(". ")
        if cut == -1 or end == n or cut < int(0.6 * len(window)):
            cut = len(window)
        chunk = window[:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = start + cut - ov_chars
        if start < 0:
            start = 0
    return chunks

def _embed_texts(texts: List[str]) -> List[List[float]]:
    # OpenAI returns normalized embeddings (suitable for cosine distance).
    resp = oai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def _insert_document(title: str, source: str, meta: Dict[str, Any], external_id: Optional[str]) -> int:
    row = fetchone(
        "INSERT INTO documents (title, source, meta, external_id) VALUES (%s,%s,%s,%s) RETURNING id;",
        (title, source, json.dumps(meta or {}), external_id),
    )
    return int(row[0])

def _upsert_doc_by_external_id(title: str, source: str, meta: Dict[str, Any], external_id: str) -> int:
    # Try to reuse existing document row if external_id already seen
    row = fetchone("SELECT id FROM documents WHERE external_id=%s;", (external_id,))
    if row:
        doc_id = int(row[0])
        # optional: update title/meta
        execute("UPDATE documents SET title=%s, source=%s, meta=%s WHERE id=%s;",
                (title, source, json.dumps(meta or {}), doc_id))
        # delete old chunks so we re-index fresh
        execute("DELETE FROM chunks WHERE document_id=%s;", (doc_id,))
        return doc_id
    return _insert_document(title, source, meta, external_id)

def _insert_chunks(doc_id: int, chunks: List[str], embeds: List[List[float]]):
    assert len(chunks) == len(embeds)
    rows = []
    for i, (txt, emb) in enumerate(zip(chunks, embeds)):
        rows.append((doc_id, i, txt, emb))
    # psycopg can adapt Python lists to vector using pgvector
    execute(
        "INSERT INTO chunks (document_id, ord, text, embedding) VALUES (%s,%s,%s,%s)",
        rows,
        many=True,
    )

def _similarity_search(query_emb: List[float], k: int = 6) -> List[Dict[str, Any]]:
    rows = fetchall(
        """
        SELECT c.document_id, c.ord, c.text, (c.embedding <=> %s::vector) AS distance,
               d.title, d.source, d.meta, d.external_id
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
        """,
        (query_emb, query_emb, k),
    )
    out = []
    for r in rows:
        out.append({
            "document_id": int(r[0]),
            "ord": int(r[1]),
            "text": r[2],
            "distance": float(r[3]),  # cosine distance (lower = closer)
            "title": r[4],
            "source": r[5],
            "meta": r[6],
            "external_id": r[7],
        })
    return out

def _fetch_url(url: str) -> Tuple[str, str]:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    content = r.text
    title = re.search(r"<title>(.*?)</title>", content, re.I|re.S)
    title_text = _clean_text(title.group(1)) if title else url
    # naive HTML strip
    text = re.sub("<[^>]+>", " ", content)
    text = _clean_text(text)
    return title_text, text

# ------------------------------
# Pydantic payloads
# ------------------------------
class IndexBody(BaseModel):
    text: Optional[str] = Field(None, description="Raw text to index")
    url: Optional[str] = Field(None, description="URL to fetch and index")
    title: Optional[str] = None
    external_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class QueryBody(BaseModel):
    query: str
    k: int = 6

class DeleteBody(BaseModel):
    document_id: Optional[int] = None
    external_id: Optional[str] = None

# ------------------------------
# Routes
# ------------------------------
@bp.route("/index", methods=["POST"])
def index_route():
    data = IndexBody.model_validate(request.get_json(force=True))
    if not (data.text or data.url):
        return jsonify({"error": "Provide 'text' or 'url'"}), 400

    if data.url:
        title, text = _fetch_url(data.url)
        source = "url"
        external_id = data.external_id or data.url
        title = data.title or title
    else:
        text = data.text or ""
        source = "text"
        external_id = data.external_id
        title = data.title or (data.external_id or f"Text@{int(time.time())}")

    chunks = _chunk_text(text)
    if not chunks:
        return jsonify({"error": "No indexable text after cleaning"}), 400

    # Make/Reuse document row (if external_id supplied)
    if external_id:
        doc_id = _upsert_doc_by_external_id(title, source, data.meta, external_id)
    else:
        doc_id = _insert_document(title, source, data.meta, external_id=None)

    embeds = _embed_texts(chunks)
    _insert_chunks(doc_id, chunks, embeds)

    return jsonify({
        "ok": True,
        "document_id": doc_id,
        "title": title,
        "chunks_indexed": len(chunks),
        "dims": EMBEDDING_DIMS,
        "model": EMBEDDING_MODEL,
    })

@bp.route("/query", methods=["POST"])
def query_route():
    data = QueryBody.model_validate(request.get_json(force=True))
    q = _clean_text(data.query)
    if not q:
        return jsonify({"error": "Empty query"}), 400
    q_emb = _embed_texts([q])[0]
    hits = _similarity_search(q_emb, k=data.k)
    # You can add a lightweight “answer synthesizer” step here if desired
    return jsonify({"matches": hits, "model": EMBEDDING_MODEL})

@bp.route("/delete", methods=["POST"])
def delete_route():
    data = DeleteBody.model_validate(request.get_json(force=True))
    if not data.document_id and not data.external_id:
        return jsonify({"error": "Provide 'document_id' or 'external_id'"}), 400

    if data.document_id:
        execute("DELETE FROM documents WHERE id=%s;", (data.document_id,))
        return jsonify({"ok": True, "deleted_document_id": data.document_id})
    else:
        row = fetchone("SELECT id FROM documents WHERE external_id=%s;", (data.external_id,))
        if not row:
            return jsonify({"ok": True, "message": "No document with that external_id"}), 200
        did = int(row[0])
        execute("DELETE FROM documents WHERE id=%s;", (did,))
        return jsonify({"ok": True, "deleted_document_id": did})

@bp.route("/docs", methods=["GET"])
def docs_route():
    rows = fetchall("SELECT id, title, source, external_id, meta, created_at FROM documents ORDER BY id DESC LIMIT 200;")
    out = []
    for r in rows:
        out.append({
            "document_id": int(r[0]),
            "title": r[1],
            "source": r[2],
            "external_id": r[3],
            "meta": r[4],
            "created_at": r[5].isoformat() if r[5] else None
        })
    return jsonify({"documents": out})
