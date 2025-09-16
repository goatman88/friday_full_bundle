# src/backend/rag_blueprint.py
from __future__ import annotations
import os
import threading
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

# local modules
from .db import fetchone, fetchall, execute
from .storage_s3 import put_bytes, presign_get_url, presign_put_url
from .jobs import create as job_create, set_status as job_set, get as job_get, bump as job_bump

# (Optional) your parsing helpers (server-side PDF/DOCX parsing)
# from pdfminer.high_level import extract_text as pdf_extract_text
# from docx import Document as DocxDocument

bp = Blueprint("rag", __name__, url_prefix="/api/rag")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

# Allowed extensions if you need to enforce
ALLOWED_EXTS = {".pdf", ".docx", ".txt"}

@bp.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "rag": "alive"})

# ---------- 1) Presign: PUT to S3 ----------
@bp.route("/upload_url", methods=["POST"])
def upload_url():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    content_type = data.get("content_type") or "application/octet-stream"
    if not filename:
        return jsonify({"ok": False, "error": "filename is required"}), 400

    # sanitize filename a bit
    safe = secure_filename(filename)
    url, s3_uri = presign_put_url(safe, content_type=content_type)
    return jsonify({"ok": True, "url": url, "s3_uri": s3_uri})

# ---------- 2) Confirm upload → background parse/index job ----------
@bp.route("/confirm_upload", methods=["POST"])
def confirm_upload():
    """
    Input JSON: { s3_uri, title, external_id }
    Returns: { ok: true, job_id }
    """
    data = request.get_json(silent=True) or {}
    s3_uri = data.get("s3_uri")
    title = data.get("title") or ""
    job_id = data.get("external_id")  # caller passes ID they’ll poll with

    if not s3_uri or not job_id:
        return jsonify({"ok": False, "error": "s3_uri and external_id are required"}), 400

    job_create(job_id, title=title)
    job_set(job_id, "processing", "Starting indexing…", progress=5)

    # kick off background work
    t = threading.Thread(target=_do_index_job, args=(job_id, s3_uri, title), daemon=True)
    t.start()

    return jsonify({"ok": True, "job_id": job_id})

def _do_index_job(job_id: str, s3_uri: str, title: str) -> None:
    """
    Do your heavy lifting here:
      - optional: fetch object head for metadata
      - write DB rows for the doc pointer
      - (if you parse now) pull bytes, extract text, embed, and insert vectors
      - update progress as you go
    """
    try:
        job_set(job_id, "processing", "Registering document…", progress=10)

        # Example DB write (adapt to your schema)
        # execute("INSERT INTO documents (external_id, title, s3_uri) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        #         (job_id, title, s3_uri))

        # ---- OPTIONAL: do parsing here (server-side) ----
        # bytes_ = get_s3_bytes(s3_uri)  # if you had a helper
        # if title.lower().endswith(".pdf"):
        #     text = pdf_extract_text(BytesIO(bytes_))
        # elif title.lower().endswith(".docx"):
        #     text = "\n".join(p.text for p in DocxDocument(BytesIO(bytes_)).paragraphs)
        # else:
        #     text = bytes_.decode("utf-8", errors="ignore")
        #
        # job_set(job_id, "processing", "Embedding chunks…", progress=70)
        # ... chunk + embed + insert into your pgvector table …
        #
        # job_set(job_id, "processing", "Finalizing…", progress=90)

        # Simulate some progress for UX (remove in production)
        for p in (30, 45, 60, 75, 90):
            job_set(job_id, "processing", f"Working… {p}%", progress=p)

        job_set(job_id, "done", "Indexed", progress=100)

    except Exception as e:
        job_set(job_id, "error", f"{type(e).__name__}: {e}", progress=100)

# ---------- 3) Poll status ----------
@bp.route("/status/<job_id>", methods=["GET"])
def status(job_id: string = ""):
    job = job_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "job": job})

# ---------- 4) Optional: presigned GET to download ----------
@bp.route("/file_url", methods=["GET"])
def file_url():
    external_id = request.args.get("external_id", "")
    if not external_id:
        return jsonify({"ok": False, "error": "external_id required"}), 400

    # Look up by external_id -> s3_uri in your DB if needed.
    # For demo, assume filename == title == external_id; adapt for your schema.
    # row = fetchone("SELECT s3_uri FROM documents WHERE external_id = %s", (external_id,))
    # if not row: return jsonify({"ok": False, "error": "not found"}), 404
    # s3_uri = row["s3_uri"]

    # If you only stored key, adjust presign_get_url(key) call accordingly.
    # Here we’ll just deny when there’s no DB linkage in this example:
    return jsonify({"ok": False, "error": "wire /file_url to your DB lookup"}), 400

# --- SSE: live job updates ---
import json, time
from flask import Response

@bp.get("/stream/<job_id>")
def stream(job_id: str):
    """
    Server-Sent Events stream for job status.
    Emits an event whenever the job changes, plus periodic heartbeats.
    """
    # tiny guard so proxies don’t buffer
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # helpful on some platforms
    }

    def gen():
        last_sent = 0.0
        heartbeat_at = time.time()
        # send initial snapshot if present
        job = job_get(job_id)
        if job:
            payload = json.dumps({"ok": True, "job": job})
            yield f"event: update\ndata: {payload}\n\n"
            last_sent = job.get("updated_at", 0.0)
        else:
            # let the client know it doesn't exist yet (maybe just created)
            payload = json.dumps({"ok": False, "error": "not_found_yet"})
            yield f"event: noop\ndata: {payload}\n\n"

        # stream until done/error, with heartbeat
        while True:
            job = job_get(job_id)
            now = time.time()

            # heartbeat every 15s
            if now - heartbeat_at >= 15:
                yield ": hb\n\n"   # comment line; keeps connection alive
                heartbeat_at = now

            if job:
                updated_at = job.get("updated_at", 0.0)
                if updated_at > last_sent:
                    payload = json.dumps({"ok": True, "job": job})
                    yield f"event: update\ndata: {payload}\n\n"
                    last_sent = updated_at

                    # stop after terminal state
                    if job.get("status") in ("done", "error"):
                        break

            time.sleep(0.8)

    return Response(gen(), headers=headers)




