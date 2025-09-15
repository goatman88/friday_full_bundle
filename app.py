import os
import io
import json
import mimetypes
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, jsonify, request, abort, Response
from flask_cors import CORS

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from openai_client import make_openai_client

# ---------------------------
# App setup
# ---------------------------
app = Flask(__name__)
CORS(app)

# --- add S3 uploads ---
from s3_uploads import bp_s3  # <<< add
app.register_blueprint(bp_s3)  # <<< add

API_TOKEN = os.getenv("API_TOKEN", "")
AWS_REGION = os.getenv("AWS_REGION") or "us-east-1"
S3_BUCKET = os.getenv("S3_BUCKET")

# OpenAI client (safe: no proxies kw)
oai = make_openai_client()

# In-memory demo store (swap to Postgres/pgvector when ready)
_DB: List[Dict[str, Any]] = []

def routes_list() -> List[str]:
    return [r.rule for r in app.url_map.iter_rules()]

def bearer_required():
    if not API_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth.split(" ", 1)[1] == API_TOKEN:
        return
    # allow token via query for /admin convenience
    if request.args.get("token") == API_TOKEN:
        return
    abort(401)

# ---------------------------
# Base + diagnostics
# ---------------------------
@app.get("/")
def root():
    return jsonify({"message": "Friday backend is running", "ok": True, "routes": routes_list()})

@app.get("/__routes")
def __routes():
    return jsonify(routes_list())

@app.get("/__whoami")
def __whoami():
    return jsonify({
        "app_id": int(datetime.utcnow().timestamp() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip() or "unknown",
    })

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

# ---------------------------
# RAG – existing endpoints
# ---------------------------
@app.post("/api/rag/index")
def rag_index():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    text = str(d.get("text") or "")
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400

    emb = oai.embeddings.create(
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        input=text
    ).data[0].embedding

    doc = {
        "id": f"doc_{int(datetime.utcnow().timestamp())}",
        "title": str(d.get("title") or ""),
        "preview": (text[:160] + "…") if len(text) > 160 else text,
        "text": text,
        "source": str(d.get("source") or "unknown"),
        "mime": str(d.get("mime") or "text/plain"),
        "user_id": str(d.get("user_id") or "public"),
        "embedding": emb,
    }
    _DB.append(doc)
    return jsonify({"ok": True, "indexed": True, "doc": {"id": doc["id"], "title": doc["title"]}})

@app.post("/api/rag/query")
def rag_query():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    q = str(d.get("query") or "")
    k = int(d.get("topk") or 3)
    if not q:
        return jsonify({"ok": False, "error": "query required"}), 400

    qv = oai.embeddings.create(
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        input=q
    ).data[0].embedding

    def score(doc): return sum(a*b for a, b in zip(doc["embedding"], qv))
    ranked = sorted(_DB, key=score, reverse=True)[:k]

    prompt = ("Use the context to answer.\n\n" +
              "\n".join(f"- {x['title']}: {x['preview']}" for x in ranked) +
              f"\n\nQ: {q}\nA:")

    ans = oai.responses.create(
        model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        input=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_output_tokens=256,
    ).output_text.strip()

    return jsonify({
        "ok": True,
        "answer": ans,
        "contexts": [{"id": x["id"], "preview": x["preview"], "title": x["title"]} for x in ranked]
    })

# ---------------------------
# Minimal text extraction from S3 (text/* & markdown only)
# ---------------------------
def _extract_text_from_bytes(data: bytes, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct.startswith("text/") or "markdown" in ct:
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("latin-1", errors="ignore")
    # For anything else we skip; you can extend later (PDF, docx, etc.)
    return ""

@app.post("/api/rag/index-from-s3")
def index_from_s3():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    key = d.get("key")
    if not key or not S3_BUCKET:
        return jsonify({"ok": False, "error": "key and S3_BUCKET required"}), 400

    s3 = boto3.client("s3", region_name=AWS_REGION, config=BotoConfig(signature_version="s3v4"))
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        body: bytes = obj["Body"].read()
        content_type = obj.get("ContentType") or mimetypes.guess_type(key)[0] or "application/octet-stream"
    except ClientError as e:
        return jsonify({"ok": False, "error": f"S3 get_object failed: {e.response['Error']['Message']}"}), 400

    text = _extract_text_from_bytes(body, content_type)
    if not text:
        return jsonify({"ok": False, "error": f"unsupported content-type for simple index: {content_type}"}), 415

    payload = {
        "title": d.get("title") or os.path.basename(key),
        "text": text,
        "source": "s3",
        "mime": content_type,
        "user_id": d.get("user_id") or "public",
    }
    # reuse existing endpoint logic
    with app.test_request_context(json=payload, headers=request.headers):
        return rag_index()

# ---------------------------
# S3 Multipart Uploads
# ---------------------------
def _s3():
    return boto3.client("s3", region_name=AWS_REGION, config=BotoConfig(signature_version="s3v4"))

@app.post("/api/uploads/initiate")
def uploads_initiate():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    filename = d.get("filename")
    content_type = d.get("contentType") or "application/octet-stream"
    prefix = d.get("prefix") or "uploads/"
    if not filename or not S3_BUCKET:
        return jsonify({"ok": False, "error": "filename and S3_BUCKET required"}), 400

    key = prefix.rstrip("/") + "/" + f"{int(datetime.utcnow().timestamp())}_{filename}"
    s3 = _s3()
    try:
        res = s3.create_multipart_upload(Bucket=S3_BUCKET, Key=key, ContentType=content_type)
    except ClientError as e:
        return jsonify({"ok": False, "error": f"initiate failed: {e.response['Error']['Message']}"}), 400

    return jsonify({"ok": True, "bucket": S3_BUCKET, "key": key, "uploadId": res["UploadId"]})

@app.post("/api/uploads/part")
def uploads_part():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    key, upload_id, part_number = d.get("key"), d.get("uploadId"), int(d.get("partNumber") or 0)
    if not (key and upload_id and part_number >= 1):
        return jsonify({"ok": False, "error": "key, uploadId, partNumber >= 1 required"}), 400
    s3 = _s3()
    try:
        url = s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={"Bucket": S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
            ExpiresIn=3600,
        )
    except ClientError as e:
        return jsonify({"ok": False, "error": f"presign part failed: {e.response['Error']['Message']}"}), 400
    return jsonify({"ok": True, "url": url})

@app.post("/api/uploads/complete")
def uploads_complete():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    key, upload_id = d.get("key"), d.get("uploadId")
    parts = d.get("parts") or []  # [{"ETag":"...", "PartNumber":1}, ...]
    if not (key and upload_id and parts):
        return jsonify({"ok": False, "error": "key, uploadId, parts[] required"}), 400
    s3 = _s3()
    try:
        s3.complete_multipart_upload(
            Bucket=S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )
    except ClientError as e:
        return jsonify({"ok": False, "error": f"complete failed: {e.response['Error']['Message']}"}), 400

    # public URL shape depends on your bucket policy; return s3:// and https form
    https_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    return jsonify({"ok": True, "key": key, "s3": f"s3://{S3_BUCKET}/{key}", "url": https_url})

@app.post("/api/uploads/abort")
def uploads_abort():
    bearer_required()
    d = request.get_json(force=True, silent=True) or {}
    key, upload_id = d.get("key"), d.get("uploadId")
    if not (key and upload_id):
        return jsonify({"ok": False, "error": "key and uploadId required"}), 400
    s3 = _s3()
    try:
        s3.abort_multipart_upload(Bucket=S3_BUCKET, Key=key, UploadId=upload_id)
    except ClientError as e:
        return jsonify({"ok": False, "error": f"abort failed: {e.response['Error']['Message']}"}), 400
    return jsonify({"ok": True, "aborted": True})

# ---------------------------
# /admin dashboard (token-gated)
# ---------------------------
_ADMIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Friday Admin</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    progress { width: 100%; }
  </style>
</head>
<body class="bg-slate-50 text-slate-900">
  <div class="max-w-5xl mx-auto p-6 space-y-6">
    <h1 class="text-2xl font-bold">Friday Admin</h1>

    <div id="auth" class="p-4 border rounded bg-white">
      <div class="flex gap-2 items-end">
        <div class="grow">
          <label class="block text-sm">API Token</label>
          <input id="token" class="w-full border rounded p-2" placeholder="Your API_TOKEN"/>
        </div>
        <button id="saveToken" class="px-4 py-2 bg-blue-600 text-white rounded">Use token</button>
      </div>
      <p class="text-xs mt-1 text-slate-600">Tip: you can also open /admin?token=... to auto-fill.</p>
    </div>

    <div class="grid md:grid-cols-2 gap-6">
      <section class="p-4 border rounded bg-white">
        <h2 class="font-semibold mb-3">Health & Routes</h2>
        <div class="flex gap-2">
          <button id="btnHealth" class="px-3 py-2 bg-slate-800 text-white rounded">/health</button>
          <button id="btnRoutes" class="px-3 py-2 bg-slate-800 text-white rounded">/__routes</button>
        </div>
        <pre id="diagOut" class="mono text-sm mt-3 whitespace-pre-wrap"></pre>
      </section>

      <section class="p-4 border rounded bg-white">
        <h2 class="font-semibold mb-3">RAG: Index</h2>
        <input id="idxTitle" class="w-full border rounded p-2 mb-2" placeholder="Title"/>
        <textarea id="idxText" class="w-full border rounded p-2 h-28" placeholder="Paste text to index"></textarea>
        <button id="btnIndex" class="mt-2 px-3 py-2 bg-green-600 text-white rounded">POST /api/rag/index</button>
        <pre id="idxOut" class="mono text-sm mt-3 whitespace-pre-wrap"></pre>
      </section>

      <section class="p-4 border rounded bg-white">
        <h2 class="font-semibold mb-3">RAG: Query</h2>
        <input id="qText" class="w-full border rounded p-2 mb-2" placeholder="Your question"/>
        <button id="btnQuery" class="px-3 py-2 bg-indigo-600 text-white rounded">POST /api/rag/query</button>
        <pre id="qOut" class="mono text-sm mt-3 whitespace-pre-wrap"></pre>
      </section>

      <section class="p-4 border rounded bg-white">
        <h2 class="font-semibold mb-3">S3 Upload (Multipart)</h2>
        <input id="fileInput" type="file" class="w-full mb-2"/>
        <div class="flex gap-2">
          <button id="btnUpload" class="px-3 py-2 bg-blue-600 text-white rounded">Upload</button>
          <button id="btnAbort" class="px-3 py-2 bg-red-600 text-white rounded">Abort</button>
        </div>
        <div class="mt-3">
          <div class="text-sm">Progress:</div>
          <progress id="prog" value="0" max="100"></progress>
        </div>
        <pre id="upOut" class="mono text-sm mt-3 whitespace-pre-wrap"></pre>
        <hr class="my-3"/>
        <div class="flex gap-2">
          <button id="btnIndexFromS3" class="px-3 py-2 bg-emerald-600 text-white rounded">Index uploaded text file</button>
        </div>
      </section>
    </div>
  </div>

<script>
const tokenEl = document.getElementById('token');
const saveToken = document.getElementById('saveToken');
const headers = () => {
  const t = localStorage.getItem('friday_token') || '';
  return t ? { 'Authorization': 'Bearer ' + t, 'Content-Type':'application/json' } : {'Content-Type':'application/json'};
};
const setOut = (id, obj) => document.getElementById(id).textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);

// Autofill token from URL if present
const urlToken = new URLSearchParams(location.search).get('token');
if (urlToken) {
  localStorage.setItem('friday_token', urlToken);
  tokenEl.value = urlToken;
}
saveToken.onclick = () => {
  localStorage.setItem('friday_token', tokenEl.value.trim());
  alert('Token saved in localStorage for this page.');
};

// Diagnostics
document.getElementById('btnHealth').onclick = async () => {
  const r = await fetch('/health', {headers: headers()});
  setOut('diagOut', await r.json());
};
document.getElementById('btnRoutes').onclick = async () => {
  const r = await fetch('/__routes', {headers: headers()});
  setOut('diagOut', await r.json());
};

// RAG Index
document.getElementById('btnIndex').onclick = async () => {
  const body = {
    title: document.getElementById('idxTitle').value || 'Untitled',
    text: document.getElementById('idxText').value || '',
    source: 'admin',
    mime: 'text/plain',
    user_id: 'public',
  };
  const r = await fetch('/api/rag/index', {method:'POST', headers: headers(), body: JSON.stringify(body)});
  setOut('idxOut', await r.json());
};

// RAG Query
document.getElementById('btnQuery').onclick = async () => {
  const body = { query: document.getElementById('qText').value || '', topk: 3 };
  const r = await fetch('/api/rag/query', {method:'POST', headers: headers(), body: JSON.stringify(body)});
  setOut('qOut', await r.json());
};

// Multipart Upload
let state = { key:null, uploadId:null, parts:[], size:0 };

async function initiate(name, type) {
  const r = await fetch('/api/uploads/initiate', {
    method:'POST',
    headers: headers(),
    body: JSON.stringify({ filename: name, contentType: type, prefix: 'uploads' })
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || 'initiate failed');
  return j; // {bucket, key, uploadId}
}

async function presignPart(key, uploadId, partNumber) {
  const r = await fetch('/api/uploads/part', {
    method:'POST',
    headers: headers(),
    body: JSON.stringify({ key, uploadId, partNumber })
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || 'presign failed');
  return j.url;
}

async function complete(key, uploadId, parts) {
  const r = await fetch('/api/uploads/complete', {
    method:'POST',
    headers: headers(),
    body: JSON.stringify({ key, uploadId, parts })
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || 'complete failed');
  return j;
}

document.getElementById('btnAbort').onclick = async () => {
  if (!state.uploadId) { alert('No active upload'); return; }
  await fetch('/api/uploads/abort', {method:'POST', headers: headers(), body: JSON.stringify({ key: state.key, uploadId: state.uploadId })});
  state = { key:null, uploadId:null, parts:[], size:0 };
  setOut('upOut', 'Aborted.');
};

document.getElementById('btnUpload').onclick = async () => {
  const f = document.getElementById('fileInput').files[0];
  if (!f) { alert('Pick a file'); return; }
  setOut('upOut', 'Starting upload…');
  const CHUNK = 5 * 1024 * 1024; // 5MB
  const totalParts = Math.ceil(f.size / CHUNK);
  document.getElementById('prog').value = 0;
  document.getElementById('prog').max = 100;

  const init = await initiate(f.name, f.type || 'application/octet-stream');
  state.key = init.key; state.uploadId = init.uploadId; state.parts = []; state.size = f.size;

  for (let partNumber = 1; partNumber <= totalParts; partNumber++) {
    const start = (partNumber - 1) * CHUNK;
    const end = Math.min(start + CHUNK, f.size);
    const blob = f.slice(start, end);

    const url = await presignPart(state.key, state.uploadId, partNumber);
    const put = await fetch(url, { method:'PUT', body: blob });
    if (!put.ok) throw new Error('PUT failed for part ' + partNumber);
    const etag = put.headers.get('ETag');
    state.parts.push({ ETag: etag?.replaceAll('"',''), PartNumber: partNumber });

    document.getElementById('prog').value = Math.round(partNumber * 100 / totalParts);
  }

  const done = await complete(state.key, state.uploadId, state.parts);
  setOut('upOut', done);
};

document.getElementById('btnIndexFromS3').onclick = async () => {
  if (!state.key) { alert('Upload a text/markdown file first'); return; }
  const r = await fetch('/api/rag/index-from-s3', {
    method:'POST',
    headers: headers(),
    body: JSON.stringify({ key: state.key })
  });
  setOut('upOut', await r.json());
};
</script>
</body>
</html>
"""

@app.get("/admin")
def admin():
    bearer_required()
    return Response(_ADMIN_HTML, mimetype="text/html")

# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))








































































