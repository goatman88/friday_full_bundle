import os, json, math, time, re
from pathlib import Path
from collections import Counter, defaultdict
from flask import Flask, request, jsonify, send_from_directory, abort

APP_ROOT = Path(__file__).parent.resolve()
STATIC_DIR = APP_ROOT / "static"
DATA_DIR   = APP_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
INDEX_FILE = DATA_DIR / "index.jsonl"

for p in (STATIC_DIR, DATA_DIR, UPLOAD_DIR):
    p.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.getenv("API_TOKEN", "").strip()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# ---------- helpers ----------

def ok(**kw):
    return jsonify({"ok": True, **kw})

def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

def require_auth():
    auth = request.headers.get("Authorization", "")
    if not API_TOKEN:
        return err("Server missing API token", 500)
    if not auth.startswith("Bearer "):
        return err("Unauthorized", 401)
    token = auth.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        return err("Unauthorized", 401)
    return None

def list_routes():
    routes = []
    for rt in app.url_map.iter_rules():
        if rt.endpoint == "static":
            continue
        routes.append({
            "rule": str(rt),
            "methods": sorted(m for m in rt.methods if m in {"GET","POST","PUT","DELETE","PATCH"}),
            "endpoint": rt.endpoint
        })
    return routes

# --- super-simple RAG store (bag-of-words cosine) ---

WORD = re.compile(r"[A-Za-z0-9_]{2,}")

def tokenize(text: str):
    return [t.lower() for t in WORD.findall(text or "")]

def bow(text: str) -> Counter:
    return Counter(tokenize(text))

def cosine(a: Counter, b: Counter) -> float:
    if not a or not b: return 0.0
    common = set(a.keys()) & set(b.keys())
    num = sum(a[t]*b[t] for t in common)
    da = math.sqrt(sum(v*v for v in a.values()))
    db = math.sqrt(sum(v*v for v in b.values()))
    return float(num/(da*db)) if da and db else 0.0

def index_write(doc: dict):
    with INDEX_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")

def index_read():
    if not INDEX_FILE.exists(): return []
    out = []
    with INDEX_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out

# ---------- pages ----------

@app.get("/")
def home():
    # simple landing with link to UI/Docs
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return html

@app.get("/health")
def health():
    return ok(status="running", key_present=bool(API_TOKEN), time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

@app.get("/__routes")
def list_routes_ep():
    # auth required
    need = require_auth()
    if need: return need
    return ok(routes=list_routes())

# ---------- chat ----------

@app.post("/chat")
def chat():
    need = require_auth()
    if need: return need

    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return err("message is required")

    # echo-style stub (plug your LLM here)
    return ok(reply=f"Friday heard: {msg}")

# ---------- uploads (re-used by RAG if you want) ----------

@app.post("/data/upload")
def upload_data():
    need = require_auth()
    if need: return need

    if "file" not in request.files:
        return err("No file uploaded")
    f = request.files["file"]
    if not f.filename:
        return err("Empty filename")

    dest = UPLOAD_DIR / f.filename
    f.save(dest)
    notes = request.form.get("notes", "")
    return ok(filename=f.filename, bytes=dest.stat().st_size, notes=notes)

# ---------- tiny RAG API ----------

@app.post("/api/rag/index")
def rag_index():
    need = require_auth()
    if need: return need

    # Accept JSON: { "title": "...", "text": "..." }
    # Optional: "source": "manual|upload|url", "meta": {...}
    data = request.get_json(silent=True) or {}
    text  = (data.get("text") or "").strip()
    title = (data.get("title") or f"note-{int(time.time())}")
    source = (data.get("source") or "manual")
    meta = data.get("meta") or {}

    if not text:
        return err("text is required")

    doc = {
        "id": f"doc_{int(time.time()*1000)}",
        "title": title,
        "text": text,
        "source": source,
        "meta": meta,
        "ts": int(time.time())
    }
    index_write(doc)
    return ok(indexed=doc["id"], title=title, chars=len(text))

@app.post("/api/rag/query")
def rag_query():
    need = require_auth()
    if need: return need

    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    k = int(data.get("k") or 3)
    if not q:
        return err("question is required")

    docs = index_read()
    if not docs:
        return ok(answer="(no notes indexed yet)", contexts=[])

    qvec = bow(q)
    scored = []
    for d in docs:
        s = cosine(qvec, bow(d.get("text","")))
        if s > 0: scored.append((s, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [{"score": round(s,4), "id": d["id"], "title": d.get("title"), "preview": (d.get("text","")[:240] + ("…" if len(d.get("text",""))>240 else ""))} for s,d in scored[:k]]

    # toy “answer”: stitch top previews (plug your LLM later)
    stitched = " | ".join(t["preview"] for t in top) or "(no match)"
    answer = f"Top {len(top)} matches → {stitched}"
    return ok(answer=answer, contexts=top)

# ---------- UI & Docs ----------

@app.get("/ui")
def serve_ui():
    # tiny chat tester (token stored in localStorage)
    return send_from_directory(STATIC_DIR, "ui.html")

@app.get("/docs")
def serve_docs():
    return send_from_directory(STATIC_DIR, "docs.html")

# ---------- static fallback ----------

@app.get("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

# ---------- main ----------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)




















































