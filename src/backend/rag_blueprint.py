# src/backend/rag_blueprint.py
from __future__ import annotations
import io, os, uuid
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from .storage_s3 import put_bytes, presign_get_url
from .db import ensure_schema, execute, fetchall

# --- Embeddings ---
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
client = OpenAI(api_key=OPENAI_API_KEY)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "1536"))

bp = Blueprint("rag", __name__, url_prefix="/api/rag")

ALLOWED_EXTS = {".pdf", ".docx", ".txt"}

# Optional parsers (best-effort)
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:
    pdf_extract_text = None

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

def _embed(text: str) -> list[float]:
    """Get embedding vector as a Python list[float]."""
    text = (text or "").strip()
    if not text:
        return [0.0] * EMBEDDING_DIMS
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    vec = resp.data[0].embedding
    # Safety: truncate/pad to EMBEDDING_DIMS
    if len(vec) > EMBEDDING_DIMS:
        vec = vec[:EMBEDDING_DIMS]
    elif len(vec) < EMBEDDING_DIMS:
        vec = vec + [0.0] * (EMBEDDING_DIMS - len(vec))
    return vec

@bp.get("/ping")
def rag_ping():
    return jsonify({"ok": True, "rag": "alive"})

@bp.post("/migrate")
def migrate():
    """Create extension, table, index."""
    try:
        ensure_schema()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/index")
def index_text():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    title = (data.get("title") or "untitled").strip()
    content = (data.get("text") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "missing text"}), 400

    ensure_schema()
    s3_uri = data.get("s3_uri") or f"s3://noop/{uuid.uuid4().hex}.txt"  # optional pointer
    emb = _embed(content)

    execute(
        """
        INSERT INTO documents (external_id, title, s3_uri, content, embedding)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (external_id) DO UPDATE
          SET title=EXCLUDED.title, s3_uri=EXCLUDED.s3_uri,
              content=EXCLUDED.content, embedding=EXCLUDED.embedding
        """,
        (data.get("external_id") or str(uuid.uuid4()), title, s3_uri, content, emb),
    )
    return jsonify({"ok": True, "title": title, "chars": len(content)})

@bp.post("/index_file")
def index_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing file"}), 400

    ensure_schema()

    f = request.files["file"]
    filename = secure_filename(f.filename or "")
    if not filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400

    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTS:
        return jsonify({"ok": False, "error": f"unsupported extension {ext}"}), 400

    raw = f.read() or b""
    s3_uri = put_bytes(raw, filename, content_type=f.mimetype or "application/octet-stream")

    # simple text extraction
    extracted = ""
    if ext == ".txt":
        try:
            extracted = raw.decode("utf-8", errors="ignore")
        except Exception:
            extracted = ""
    elif ext == ".pdf" and pdf_extract_text:
        try:
            extracted = pdf_extract_text(io.BytesIO(raw))
        except Exception:
            extracted = ""
    elif ext == ".docx" and DocxDocument:
        try:
            doc = DocxDocument(io.BytesIO(raw))
            extracted = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            extracted = ""

    emb = _embed(extracted or filename)
    external_id = request.form.get("external_id") or str(uuid.uuid4())
    title = request.form.get("title") or filename

    execute(
        """
        INSERT INTO documents (external_id, title, s3_uri, content, embedding)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (external_id) DO UPDATE
          SET title=EXCLUDED.title, s3_uri=EXCLUDED.s3_uri,
              content=EXCLUDED.content, embedding=EXCLUDED.embedding
        """,
        (external_id, title, s3_uri, extracted, emb),
    )

    return jsonify({
        "ok": True,
        "external_id": external_id,
        "filename": filename,
        "bytes": len(raw),
        "s3_uri": s3_uri,
        "extracted_preview": (extracted or "")[:400],
    })

@bp.get("/file_url")
def file_url():
    s3_uri = request.args.get("s3_uri") or request.args.get("external_id")
    if not s3_uri:
        return jsonify({"ok": False, "error": "missing s3_uri"}), 400
    # If they passed external_id, look up the s3_uri
    if s3_uri.startswith("s3://"):
        pointer = s3_uri
    else:
        row = fetchall("SELECT s3_uri FROM documents WHERE external_id = %s LIMIT 1", (s3_uri,))
        if not row:
            return jsonify({"ok": False, "error": "external_id not found"}), 404
        pointer = row[0][0]
    try:
        url = presign_get_url(pointer, expires_seconds=600)
        return jsonify({"ok": True, "url": url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/query")
def query():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or 5)
    if not q:
        return jsonify({"ok": False, "error": "missing query"}), 400

    ensure_schema()
    qvec = _embed(q)

    rows = fetchall(
        """
        SELECT external_id, title, s3_uri, LEFT(content, 500) AS preview,
               1 - (embedding <=> %s::vector) AS score   -- cosine similarity (0..1)
        FROM documents
        ORDER BY embedding <=> %s::vector   -- cosine distance (lower = closer)
        LIMIT %s
        """,
        (qvec, qvec, k),
    )
    hits = [
        {
            "external_id": r[0],
            "title": r[1],
            "s3_uri": r[2],
            "content_preview": r[3],
            "score": float(r[4]),
        }
        for r in rows
    ]
    return jsonify({"ok": True, "query": q, "k": k, "hits": hits})



