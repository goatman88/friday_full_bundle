# src/app.py
from __future__ import annotations

import os
import sys
import json
import math
import time
import uuid
import platform
import logging
from typing import Dict, List, Any, Tuple

from flask import Flask, jsonify, request

# ---- Logging (fixes "Unknown level: 'info'") ----
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("friday")

# ---- Flask app ----
app = Flask(__name__)

# ---- OpenAI client (no proxies kw) ----
# Requires OPENAI_API_KEY in env
try:
    from openai import OpenAI  # openai>=1.0
    _OAI = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    _EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
except Exception as e:
    _OAI = None
    _EMBED_MODEL = None
    log.warning("OpenAI client not initialized: %s", e)

# =====================================================================================
#                                   UTIL ROUTES
# =====================================================================================

@app.route("/")
def root():
    return jsonify(
        ok=True,
        service="friday",
        message="It works. See /health, /__routes, /__whoami."
    )

@app.route("/__routes")
def _routes():
    rules = sorted([str(r.rule) for r in app.url_map.iter_rules()])
    return jsonify(rules)

@app.route("/__whoami")
def whoami():
    return jsonify({
        "app_id": int(time.time() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {platform.python_version()}",
    })

@app.route("/health")
def health():
    return jsonify(ok=True, status="running")

@app.route("/ping")
def ping():
    return jsonify(pong=True, ts=int(time.time()))

# =====================================================================================
#                                   RAG (in-memory)
# =====================================================================================
# A tiny, dependency-free vector store so your smoke tests pass without Postgres.
# Data shape:
#   _DOCS = [
#     {"id": "...", "title": "...", "text": "...", "source": "...",
#      "user_id": "...", "mime": "text/plain", "embedding": [floats]}
#   ]

_DOCS: List[Dict[str, Any]] = []

def _embed(text: str) -> List[float]:
    if _OAI is None:
        raise RuntimeError("OpenAI client not available; set OPENAI_API_KEY.")
    resp = _OAI.embeddings.create(model=_EMBED_MODEL, input=text)
    return resp.data[0].embedding  # type: ignore[attr-defined]

def _cosine(a: List[float], b: List[float]) -> float:
    # Pure-python cosine to avoid numpy dependency
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    return (dot / denom) if denom else 0.0

@app.post("/api/rag/index")
def rag_index():
    """
    Body (JSON):
      {
        "title": "Widget FAQ",
        "text": "Widgets are blue...",
        "source": "faq",
        "mime": "text/plain",
        "user_id": "public",
        "metadata": {...}   # optional
      }
    """
    body = request.get_json(force=True) or {}
    title = body.get("title") or ""
    text = body.get("text") or ""
    source = body.get("source") or "unknown"
    mime = body.get("mime") or "text/plain"
    user_id = body.get("user_id") or "public"
    metadata = body.get("metadata") or {}

    if not text.strip():
        return jsonify(ok=False, error="text is required"), 400

    emb = _embed(text)
    doc = {
        "id": str(uuid.uuid4()),
        "title": title,
        "text": text,
        "source": source,
        "mime": mime,
        "user_id": user_id,
        "metadata": metadata,
        "embedding": emb,
    }
    _DOCS.append(doc)
    return jsonify(ok=True, id=doc["id"], count=len(_DOCS))

@app.post("/api/rag/query")
def rag_query():
    """
    Body (JSON):
      { "query": "What color are widgets?", "topk": 3 }
    """
    body = request.get_json(force=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or 3)

    if not query:
        return jsonify(ok=False, error="query is required"), 400
    if not _DOCS:
        return jsonify(ok=True, results=[], note="index is empty")

    qvec = _embed(query)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for d in _DOCS:
        s = _cosine(qvec, d["embedding"])
        scored.append((s, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, d in scored[: max(1, topk)]:
        results.append({
            "id": d["id"],
            "title": d["title"],
            "source": d["source"],
            "score": round(float(score), 6),
            "text": d["text"],
            "metadata": d.get("metadata", {}),
        })
    return jsonify(ok=True, results=results)

# =====================================================================================
#                                   S3 UPLOADS
# =====================================================================================
# Env required: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, (optional) AWS_REGION,
#               S3_BUCKET
# We use boto3 to generate presigned *PUT* and multipart URLs.

_S3_BUCKET = os.environ.get("S3_BUCKET")
_AWS_REGION = os.environ.get("AWS_REGION") or "us-east-1"

try:
    import boto3
    _S3 = boto3.client("s3", region_name=_AWS_REGION)
except Exception as e:
    _S3 = None
    log.warning("boto3 S3 client not initialized: %s", e)

def _need_s3() -> Tuple[bool, Any]:
    if _S3 is None:
        return False, ("S3 client not available (check AWS creds / boto3).", 500)
    if not _S3_BUCKET:
        return False, ("S3_BUCKET env var is required.", 500)
    return True, None

@app.post("/api/s3/sign")
def s3_sign_single_put():
    """
    Body: { "key": "uploads/myfile.bin", "content_type": "application/octet-stream" }
    Returns: { "url": "...", "method": "PUT" }
    """
    ok, err = _need_s3()
    if not ok:
        msg, code = err
        return jsonify(ok=False, error=msg), code

    data = request.get_json(force=True) or {}
    key = data.get("key")
    content_type = data.get("content_type") or "application/octet-stream"
    if not key:
        return jsonify(ok=False, error="key is required"), 400

    try:
        url = _S3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": _S3_BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=3600,
        )
        return jsonify(ok=True, method="PUT", url=url, bucket=_S3_BUCKET, key=key)
    except Exception as e:
        log.exception("Failed to presign PUT: %s", e)
        return jsonify(ok=False, error=str(e)), 500

@app.post("/api/s3/multipart/create")
def s3_multipart_create():
    """
    Body: { "key": "uploads/big.bin", "content_type": "application/octet-stream" }
    Returns: { "upload_id": "...", "bucket": "...", "key": "..." }
    """
    ok, err = _need_s3()
    if not ok:
        msg, code = err
        return jsonify(ok=False, error=msg), code

    data = request.get_json(force=True) or {}
    key = data.get("key")
    content_type = data.get("content_type") or "application/octet-stream"
    if not key:
        return jsonify(ok=False, error="key is required"), 400

    try:
        resp = _S3.create_multipart_upload(Bucket=_S3_BUCKET, Key=key, ContentType=content_type)
        return jsonify(ok=True, upload_id=resp["UploadId"], bucket=_S3_BUCKET, key=key)
    except Exception as e:
        log.exception("Failed to create multipart upload: %s", e)
        return jsonify(ok=False, error=str(e)), 500

@app.post("/api/s3/multipart/part")
def s3_multipart_part():
    """
    Body: { "key": "...", "upload_id": "...", "part_number": 1 }
    Returns: { "url": "..." }
    """
    ok, err = _need_s3()
    if not ok:
        msg, code = err
        return jsonify(ok=False, error=msg), code

    data = request.get_json(force=True) or {}
    key = data.get("key")
    upload_id = data.get("upload_id")
    part_number = int(data.get("part_number") or 0)
    if not key or not upload_id or part_number <= 0:
        return jsonify(ok=False, error="key, upload_id and positive part_number are required"), 400

    try:
        url = _S3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": _S3_BUCKET,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=3600,
        )
        return jsonify(ok=True, url=url)
    except Exception as e:
        log.exception("Failed to presign part: %s", e)
        return jsonify(ok=False, error=str(e)), 500

@app.post("/api/s3/multipart/complete")
def s3_multipart_complete():
    """
    Body:
      {
        "key": "...",
        "upload_id": "...",
        "parts": [ {"ETag": "\"etag1..\"", "PartNumber": 1}, ... ]
      }
    Returns S3 completion result.
    """
    ok, err = _need_s3()
    if not ok:
        msg, code = err
        return jsonify(ok=False, error=msg), code

    data = request.get_json(force=True) or {}
    key = data.get("key")
    upload_id = data.get("upload_id")
    parts = data.get("parts") or []
    if not key or not upload_id or not parts:
        return jsonify(ok=False, error="key, upload_id, and parts[] are required"), 400

    try:
        resp = _S3.complete_multipart_upload(
            Bucket=_S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        return jsonify(ok=True, result=resp)
    except Exception as e:
        log.exception("Failed to complete multipart upload: %s", e)
        return jsonify(ok=False, error=str(e)), 500


# =====================================================================================
#                                ENTRY POINT (local)
# =====================================================================================
if __name__ == "__main__":
    # For local debugging only; on Render we run via waitress using wsgi:app
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)















































































