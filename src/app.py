import os
import time
import json
import logging
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─── OpenAI client (NO proxies kw) ─────────────────────────────────────────────
# Uses the modern SDK import path. If OPENAI_API_KEY is absent, we still boot.
try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    _openai_client = None

# ─── App + CORS ────────────────────────────────────────────────────────────────
def _allowed_origins() -> List[str]:
    """
    FRONTEND_ORIGIN   e.g. https://my-frontend.onrender.com
    CORS_EXTRA_ORIGINS e.g. https://foo.com,https://bar.com
    DEV fallback      http://localhost:5173 http://localhost:3000
    """
    explicit = os.getenv("FRONTEND_ORIGIN")
    extras = os.getenv("CORS_EXTRA_ORIGINS", "")
    devs = ["http://localhost:3000", "http://localhost:5173"]
    origins = [o.strip() for o in [explicit, *extras.split(","), *devs] if o and o.strip()]
    # If you truly want to allow everything, set CORS_ALLOW_ALL=1
    if os.getenv("CORS_ALLOW_ALL") == "1":
        return ["*"]
    return sorted(set(origins)) or ["*"]  # permissive default if nothing set

app = Flask(__name__, static_folder="static", static_url_path="/static")

CORS(
    app,
    resources={r"/*": {"origins": _allowed_origins()}},
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS"],
    max_age=86400,
)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("friday.app")

# ─── Super tiny in-memory “RAG store” just for smoke tests ────────────────────
# (Keeps parity with your PowerShell test script.)
_DOCS: List[Dict[str, Any]] = []

def _index_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    # Minimal schema normalizer for your smoke test body
    item = {
        "id": doc.get("id") or f"d{len(_DOCS)+1}",
        "title": doc.get("title") or "Untitled",
        "text": doc.get("text") or "",
        "source": doc.get("source") or "misc",
        "mime": doc.get("mime") or "text/plain",
        "user_id": doc.get("user_id") or "public",
        "ts": time.time(),
    }
    _DOCS.append(item)
    return item

def _keyword_search(q: str, topk: int = 3) -> List[Dict[str, Any]]:
    ql = q.lower().strip()
    ranked = sorted(
        _DOCS,
        key=lambda d: (d["text"].lower().count(ql) + d["title"].lower().count(ql), d["ts"]),
        reverse=True,
    )
    return ranked[: max(1, min(topk, 20))]

# ─── Utility endpoints ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return jsonify({"ok": True, "service": "friday", "status": "running"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

@app.get("/__routes")
def routes():
    """List registered routes — handy for smoke tests."""
    rules = sorted([str(r.rule) for r in app.url_map.iter_rules()])
    return jsonify(rules)

@app.get("/__whoami")
def whoami():
    here = {
        "app_id": os.getenv("RENDER_SERVICE_ID") or os.getenv("DYNO") or "local",
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}",
    }
    return jsonify(here)

# ─── Static passthrough (optional) ─────────────────────────────────────────────
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ─── RAG: index & query (smoke-test compatible) ───────────────────────────────
@app.post("/api/rag/index")
def rag_index():
    try:
        body = request.get_json(force=True, silent=False) or {}
        item = _index_doc(body)
        return jsonify({"ok": True, "indexed": item}), 201
    except Exception as e:
        log.exception("index failed")
        return jsonify({"ok": False, "error": str(e)}), 400

@app.post("/api/rag/query")
def rag_query():
    try:
        body = request.get_json(force=True, silent=False) or {}
        q = str(body.get("query") or "").strip()
        topk = int(body.get("topk") or 3)
        matches = _keyword_search(q, topk=topk)
        # Optional: if OpenAI key is present, create a short answer using context
        answer = None
        if _openai_client and q and matches:
            ctx_snips = "\n\n".join(
                [f"[{m['title']}]\n{m['text'][:1000]}" for m in matches]
            )
            prompt = (
                "You are a concise assistant. Answer the user using ONLY the context.\n\n"
                f"Context:\n{ctx_snips}\n\nQuestion: {q}\nAnswer:"
            )
            try:
                resp = _openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                answer = resp.choices[0].message.content
            except Exception as oe:
                # Don’t fail the endpoint if OpenAI is unavailable
                log.warning("OpenAI call failed: %s", oe)
                answer = None

        preview = [
            {
                "id": m["id"],
                "title": m["title"],
                "preview": (m["text"][:140] + "…") if len(m["text"]) > 140 else m["text"],
                "score": 1.0,  # dummy score (keyword search)
                "source": m["source"],
            }
            for m in matches
        ]
        return jsonify({"ok": True, "answer": answer, "contexts": preview})
    except Exception as e:
        log.exception("query failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ─── Entry point for local runs ────────────────────────────────────────────────
if __name__ == "__main__":
    # Local dev server (Render runs waitress/WSGI)
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")













































































