# app.py  — Friday backend (Render + Local)
# ----------------------------------------
# Endpoints:
#   GET  /health               -> service & key check
#   POST /chat                 -> "Einstein" problem-solver w/ OpenAI or local fallback
#   POST /data/upload          -> add a local file to the library (CSV/TXT/PDF)
#
# Notes:
# - Put your .env next to this file:
#     OPENAI_API_KEY=sk-...
#     OPENAI_MODEL=gpt-4o-mini
# - On Render, set the same variables in the service Environment tab.

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --------- App setup ---------
APP_DIR = Path(__file__).parent.resolve()
STORAGE_DIR = APP_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
INGESTED_PATH = STORAGE_DIR / "ingested.json"      # your “library index”

for p in (STORAGE_DIR, UPLOADS_DIR):
    p.mkdir(parents=True, exist_ok=True)

load_dotenv()  # load .env (local); Render uses service env

def get_model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def have_key() -> bool:
    key = os.getenv("OPENAI_API_KEY") or ""
    return bool(key.strip())

# Lazy OpenAI client import so the app can boot without the package when falling back
def make_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
CORS(app)

# --------- Small helpers ---------
def load_ingested() -> Dict[str, Any]:
    """Return the ingested.json contents if present, else an empty skeleton."""
    if INGESTED_PATH.is_file():
        try:
            return json.loads(INGESTED_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"count": 0, "files": [], "errors": []}

def summarize_library_locally(max_items: int = 25) -> str:
    """Very simple local summary of files from ingested.json."""
    data = load_ingested()
    files = data.get("files", [])
    total = data.get("count", len(files))
    parts = [f"OpenAI unavailable; giving a local answer.\n"]
    if not files:
        parts.append("I don’t see any indexed files yet. Try an ingest step first.")
        return "\n".join(parts)

    parts.append("Problem summary: Summarize what you ingested.\n")
    shown = files[:max_items]
    for f in shown:
        name = f.get("name") or f.get("title") or "unknown"
        mtype = f.get("mimeType") or "file"
        size = f.get("size")
        size_str = f" ({size} bytes)" if size is not None else ""
        parts.append(f"- {name} [{mtype}]{size_str}")
    parts.append(f"\nTotal files indexed: {total}.")
    return "\n".join(parts)

EINSTEIN_SYSTEM = """You are Friday — a calm, practical 'Einstein-grade' problem solver.
Traits: precise, non-aggressive, optimistic, and very concrete.
When answering:
- Start with a 1–2 sentence insight or summary.
- Then produce a short action plan: 3–7 steps max.
- Use a quick 'Impact x Effort' matrix: list 2–4 items in High Impact/Low Effort first.
- If data is provided, analyze it (call out caveats and assumptions).
- Keep it helpful and real-world; avoid fluff."""

def build_library_context(limit: int = 40) -> str:
    """Lightweight context string of file names to condition the model."""
    data = load_ingested()
    files = data.get("files", [])
    if not files:
        return "No library files were found."
    names = []
    for f in files[:limit]:
        names.append(f.get("name") or f.get("title") or "unknown")
    return "Indexed library files (sample): " + ", ".join(names)

# --------- Routes ---------
@app.get("/")
def root():
    return jsonify({"ok": True, "msg": "Friday backend is running.", "endpoints": ["/health", "/chat", "/data/upload"]})

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "debug": {
            "key_present": have_key(),
            "model": get_model_name(),
        }
    })

@app.get("/diag/openai")
def diag_openai():
    """Optional: quick OpenAI key sanity on the server."""
    if not have_key():
        return jsonify({"ok": False, "reason": "No OPENAI_API_KEY visible to server."}), 200
    try:
        client = make_openai_client()
        # Light no-op call (model listing is disabled on some accounts; do a tiny completion instead)
        _ = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
            temperature=0.0,
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200

@app.post("/chat")
def chat():
    t0 = time.time()
    payload = request.get_json(force=True, silent=True) or {}
    user_msg = (payload.get("message") or "").strip()
    if not user_msg:
        return jsonify({"ok": False, "error": "Missing 'message' in JSON body"}), 400

    used_openai = False
    reply_text = None
    debug: Dict[str, Any] = {"key_present": have_key(), "model": get_model_name()}

    # Try OpenAI first if key present
    if have_key():
        try:
            client = make_openai_client()
            library_hint = build_library_context()
            messages = [
                {"role": "system", "content": EINSTEIN_SYSTEM},
                {"role": "user", "content": f"{user_msg}\n\nContext:\n{library_hint}"}
            ]
            res = client.chat.completions.create(
                model=get_model_name(),
                messages=messages,
                temperature=0.2,
                max_tokens=700,
            )
            reply_text = res.choices[0].message.content.strip()
            used_openai = True
        except Exception as e:
            # Fall back to local summary if anything goes wrong
            debug["openai_error"] = str(e)
            reply_text = summarize_library_locally()

    # Fallback path if no key or API failed
    if reply_text is None:
        reply_text = summarize_library_locally()

    return jsonify({
        "ok": True,
        "reply": reply_text,
        "used_openai": used_openai,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "debug": debug
    })

@app.post("/data/upload")
def data_upload():
    """
    Register a local file into Friday's library folder.
    Body JSON:
      { "path": "C:\\Users\\me\\Downloads\\file.pdf" }  # absolute
      or
      { "path": "relative/or/filename.txt" }            # relative to app folder

    We don't do heavy parsing here — we just validate + record in ingested.json
    so Friday can reference it later.
    """
    body = request.get_json(force=True, silent=True) or {}
    src = (body.get("path") or "").strip()
    if not src:
        return jsonify({"ok": False, "error": "Provide 'path' in body."}), 400

    src_path = Path(src)
    if not src_path.is_absolute():
        src_path = (APP_DIR / src_path).resolve()

    if not src_path.exists() or not src_path.is_file():
        return jsonify({"ok": False, "error": f"File not found: {src_path}"}), 400

    # Copy (or fast-path if already under uploads)
    dest_path = (UPLOADS_DIR / src_path.name).resolve()
    try:
        if src_path != dest_path:
            dest_path.write_bytes(src_path.read_bytes())
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to copy: {e}"}), 500

    # Update ingested.json (append if not present)
    lib = load_ingested()
    files: List[Dict[str, Any]] = lib.get("files", [])
    entry = next((f for f in files if f.get("name") == dest_path.name), None)
    meta = {
        "name": dest_path.name,
        "path": str(dest_path),
        "size": dest_path.stat().st_size,
        "mimeType": guess_mime(dest_path.suffix),
        "source": "upload",
    }
    if entry:
        entry.update(meta)
    else:
        files.append(meta)
    lib["files"] = files
    lib["count"] = len(files)

    try:
        INGESTED_PATH.write_text(json.dumps(lib, indent=2), encoding="utf-8")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to update library: {e}"}), 500

    return jsonify({"ok": True, "saved": meta})

def guess_mime(suffix: str) -> str:
    s = (suffix or "").lower()
    if s in [".txt", ".md", ".log"]: return "text/plain"
    if s == ".pdf": return "application/pdf"
    if s in [".csv", ".tsv"]: return "text/csv"
    if s in [".json"]: return "application/json"
    return "application/octet-stream"

# --- Upload / Ingest ---------------------------------------------------------
import os, json, io
from datetime import datetime
from flask import request, jsonify
from werkzeug.utils import secure_filename

# Optional helpers for simple text extraction
try:
    import pypdf  # for PDFs
except Exception:
    pypdf = None
try:
    import pandas as pd  # for CSV
except Exception:
    pd = None

# 1) Config & folders
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
INGEST_INDEX = os.path.join(os.path.dirname(__file__), "data", "ingested.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(INGEST_INDEX), exist_ok=True)

# Accept up to 200 MB per request (tweak if needed)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

ALLOWED_EXTS = {".pdf", ".txt", ".csv", ".md", ".json"}

def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTS

def _read_text(path: str) -> str:
    """
    Lightweight text extraction:
      - PDF: concat pages (pypdf)
      - CSV: head + basic to_markdown (pandas)
      - TXT/MD/JSON: as plain text
    """
    ext = os.path.splitext(path.lower())[1]
    try:
        if ext == ".pdf":
            if not pypdf:
                return "(pypdf not installed; stored file only)"
            text = []
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for i, page in enumerate(reader.pages[:50]):  # cap to first 50 pages for speed
                    try:
                        text.append(page.extract_text() or "")
                    except Exception:
                        text.append("")
            return "\n".join(text)

        elif ext == ".csv":
            if not pd:
                return "(pandas not installed; stored file only)"
            # Read at most first ~5000 rows for preview to avoid huge memory usage
            df = pd.read_csv(path, nrows=5000)
            # Return a compact, human-friendly sample
            sample = df.head(20).to_markdown(index=False)
            return f"CSV columns: {list(df.columns)}\n\nSample (first 20 rows):\n{sample}"

        elif ext in (".txt", ".md"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext == ".json":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        else:
            return ""
    except Exception as e:
        return f"(error reading content: {e})"

def _append_ingest_index(record: dict) -> None:
    # Append a record to data/ingested.json (creates file if missing)
    try:
        if os.path.exists(INGEST_INDEX):
            with open(INGEST_INDEX, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        else:
            data = []
    except Exception:
        data = []
    data.append(record)
    with open(INGEST_INDEX, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/data/upload", methods=["POST"])
def data_upload():
    """
    Upload a single file (multipart) OR point to an existing path (JSON).
    Response:
      { ok, path, name, bytes, kind, preview }
    """
    try:
        saved_path = None
        fname = None
        kind = None
        size = None

        # A) multipart/form-data (Postman "Body" -> "form-data", key: file, type: File)
        if "file" in request.files:
            file = request.files["file"]
            if not file or file.filename == "":
                return jsonify({"ok": False, "error": "no file uploaded"}), 400

            fname = secure_filename(file.filename)
            if not _ext_ok(fname):
                return jsonify({"ok": False, "error": f"unsupported extension. Allowed: {sorted(ALLOWED_EXTS)}"}), 400

            saved_path = os.path.join(UPLOAD_DIR, fname)
            file.save(saved_path)
            size = os.path.getsize(saved_path)
            kind = os.path.splitext(fname)[1].lstrip(".")

        # B) JSON: { "path": "C:\\Users\\me\\Downloads\\something.pdf" }
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            given = body.get("path")
            if not given:
                return jsonify({"ok": False, "error": "provide multipart 'file' or JSON {'path': ...}"}), 400
            if not os.path.isfile(given):
                return jsonify({"ok": False, "error": f"file not found: {given}"}), 400

            fname = secure_filename(os.path.basename(given))
            if not _ext_ok(fname):
                return jsonify({"ok": False, "error": f"unsupported extension. Allowed: {sorted(ALLOWED_EXTS)}"}), 400

            saved_path = os.path.join(UPLOAD_DIR, fname)
            # Copy file contents
            with open(given, "rb") as src, open(saved_path, "wb") as dst:
                dst.write(src.read())
            size = os.path.getsize(saved_path)
            kind = os.path.splitext(fname)[1].lstrip(".")

        else:
            return jsonify({"ok": False, "error": "use multipart (file) or JSON {'path': ...}"}), 400

        # Extract a compact preview (does not index full text here — just a sanity check)
        preview = _read_text(saved_path)
        if preview and len(preview) > 2000:
            preview = preview[:2000] + "\n...[truncated]..."

        # Record to ingested index
        record = {
            "name": fname,
            "path": saved_path,
            "bytes": size,
            "kind": kind,
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        }
        _append_ingest_index(record)

        return jsonify({
            "ok": True,
            "name": fname,
            "path": saved_path,
            "bytes": size,
            "kind": kind,
            "preview": preview or "(no preview)",
        })

    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)}), 500


# --------- Local dev entrypoint (optional) ---------
if __name__ == "__main__":
    # Local: python app.py
    # Render will use gunicorn/waitress via Start Command
    app.run(host="127.0.0.1", port=5000, debug=True)



































