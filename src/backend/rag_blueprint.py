# src/backend/rag_blueprint.py
from __future__ import annotations
import io
import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

# ✅ RELATIVE imports so we always load from src/backend/
from .storage_s3 import put_bytes, presign_get_url
# If you have DB helpers, keep them relative too:
# from .db import fetchone, fetchall, execute

# Optional parsers (safe to keep; comment out if not installed)
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

@bp.post("/index")
def index_text():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "untitled").strip()
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400
    # TODO: your vector insert logic here; for now just echo
    return jsonify({"ok": True, "title": title, "chars": len(text)})

@bp.post("/index_file")
def index_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400

    filename = secure_filename(f.filename)
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTS:
        return jsonify({"ok": False, "error": f"unsupported extension {ext}"}), 400

    raw = f.read() or b""
    # store original file in S3
    s3_uri = put_bytes(raw, filename, content_type=f.mimetype or "application/octet-stream")

    # very simple text extraction for PDF/DOCX/TXT
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
            extracted = "\n".join([p.text for p in doc.paragraphs])
        except Exception:
            extracted = ""

    # TODO: upsert to your vector DB here with extracted text
    # For now, just return the S3 pointer & basic stats
    return jsonify({
        "ok": True,
        "filename": filename,
        "bytes": len(raw),
        "s3_uri": s3_uri,
        "extracted_preview": extracted[:400]
    })

@bp.get("/file_url")
def file_url():
    """
    Expect query param:
      - external_id OR s3_uri
    If you stored S3 pointer as s3_uri meta, pass it back here for presign.
    """
    s3_uri = request.args.get("s3_uri")
    if not s3_uri:
        # also accept external_id if you stored the s3_uri using that
        s3_uri = request.args.get("external_id")
    if not s3_uri:
        return jsonify({"ok": False, "error": "missing s3_uri"}), 400

    try:
        url = presign_get_url(s3_uri, expires_seconds=600)
        return jsonify({"ok": True, "url": url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/query")
def query():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or 5)
    if not q:
        return jsonify({"ok": False, "error": "missing query"}), 400
    # TODO: actually query your vector DB
    return jsonify({"ok": True, "query": q, "k": k, "hits": []})

