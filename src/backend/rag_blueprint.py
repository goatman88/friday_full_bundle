# src/backend/rag_blueprint.py
from __future__ import annotations
import io, os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

# ✅ RELATIVE import inside backend package
from .storage_s3 import put_bytes, presign_get_url

# Optional parsers
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:
    pdf_extract_text = None

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

bp = Blueprint("rag", __name__, url_prefix="/api/rag")

ALLOWED_EXTS = {".pdf", ".docx", ".txt"}

@bp.get("/ping")
def rag_ping():
    return jsonify({"ok": True, "rag": "alive"})

@bp.post("/index_file")
def index_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing file"}), 400

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

    return jsonify({
        "ok": True,
        "filename": filename,
        "bytes": len(raw),
        "s3_uri": s3_uri,
        "extracted_preview": extracted[:400],
    })

@bp.get("/file_url")
def file_url():
    # Accept s3_uri (or external_id if that's what you stored)
    s3_uri = request.args.get("s3_uri") or request.args.get("external_id")
    if not s3_uri:
        return jsonify({"ok": False, "error": "missing s3_uri"}), 400
    try:
        url = presign_get_url(s3_uri, expires_seconds=600)
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
    # TODO: hook up vector search
    return jsonify({"ok": True, "query": q, "k": k, "hits": []})


