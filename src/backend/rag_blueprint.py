# src/backend/rag_blueprint.py
from __future__ import annotations
import io, os, uuid
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from .storage_s3 import put_bytes, presign_put_url, presign_get_url
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
    text = (text or "").strip()
    if not text:
        return [0.0] * EMBEDDING_DIMS
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    vec = resp.data[0].embedding
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
    s3_uri = data.get("s3_uri") or f"s3://noop/{uuid.uuid4().hex}.txt"
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

# ---------- NEW: DIRECT-TO-S3 UPLOAD FLOW ----------

@bp.post("/upload_url")
def upload_url():
    """
    Request a presigned PUT URL to upload directly to S3 from the browser.
    Body (JSON or form):
      - filename (required)
      - content_type (optional, default application/octet-stream)
      - expires (optional seconds, default 600)
    Returns: { ok, url, s3_uri, expires }
    """
    data = request.get_json(silent=True) or request.form or {}
    filename = secure_filename((data.get("filename") or "").strip())
    if not filename:
        return jsonify({"ok": False, "error": "missing filename"}), 400

    content_type = (data.get("content_type") or "application/octet-stream").strip()
    expires = int(data.get("expires") or 600)

    try:
        url, s3_uri = presign_put_url(filename=filename, content_type=content_type, expires_seconds=expires)
        return jsonify({"ok": True, "url": url, "s3_uri": s3_uri, "expires": expires})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/confirm_upload")
def confirm_upload():
    """
    Call this AFTER the browser PUTs the file to S3.
    Body JSON:
      - s3_uri (required)
      - title (optional)
      - external_id (optional)
      - content (optional) -> if you already extracted text client-side
    Behavior: fetches nothing from S3 (no GET); just stores pointer + embeds 'content' if provided.
    """
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    s3_uri = (data.get("s3_uri") or "").strip()
    if not s3_uri.startswith("s3://"):
        return jsonify({"ok": False, "error": "missing or invalid s3_uri"}), 400

    ensure_schema()
    title = (data.get("title") or os.path.basename(s3_uri)).strip()
    external_id = data.get("external_id") or str(uuid.uuid4())
    content = (data.get("content") or "").strip()  # optional
    emb = _embed(content or title)

    execute(
        """
        INSERT INTO documents (external_id, title, s3_uri, content, embedding)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (external_id) DO UPDATE
          SET title=EXCLUDED.title, s3_uri=EXCLUDED.s3_uri,
              content=EXCLUDED.content, embedding=EXCLUDED.embedding
        """,
        (external_id, title, s3_uri, content, emb),
    )
    return jsonify({"ok": True, "external_id": external_id, "s3_uri": s3_uri, "title": title})

# ---------- Existing endpoints ----------

@bp.get("/file_url")
def file_url():
    s3_uri = request.args.get("s3_uri") or request.args.get("external_id")
    if not s3_uri:
        return jsonify({"ok": False, "error": "missing s3_uri"}), 400
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
               1 - (embedding <=> %s::vector) AS score
        FROM documents
        ORDER BY embedding <=> %s::vector
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




