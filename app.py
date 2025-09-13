import os
import math
from datetime import datetime, timezone
from typing import List, Dict, Any
from flask import Flask, request, jsonify

app = Flask(__name__)

# -------------------------------------------------------------------
# Config / Auth
# -------------------------------------------------------------------
API_TOKEN = os.getenv("API_TOKEN", "changeme")

def require_auth() -> bool:
    """Return True if Authorization: Bearer <token> matches API_TOKEN."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:].strip()
    return token == API_TOKEN

def auth_or_401():
    if not require_auth():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

# -------------------------------------------------------------------
# Simple in-memory “index” for demo RAG (good enough for tests)
# NOTE: this resets on each deploy; that’s fine for quick checks.
# -------------------------------------------------------------------
_DOCS: List[Dict[str, Any]] = []

def _cosine_sim(a: Dict[str, int], b: Dict[str, int]) -> float:
    # super tiny bag-of-words similarity for demo purposes
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def _bow(text: str) -> Dict[str, int]:
    bag: Dict[str, int] = {}
    for w in (text or "").lower().split():
        bag[w] = bag.get(w, 0) + 1
    return bag

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.get("/")  # quick landing
def home():
    return "Friday backend is running."

@app.get("/health")
def health():  # make sure this function name appears only ONCE
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    key_present = bool(os.getenv("OPENAI_API_KEY"))
    return jsonify({
        "ok": True,
        "status": "running",
        "time": now,
        "key_present": key_present
    }), 200

@app.get("/__routes")
def list_routes():
    # Protected: requires Bearer token
    auth_fail = auth_or_401()
    if auth_fail:
        return auth_fail
    out = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        out.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","PUT","DELETE","PATCH"}),
            "rule": str(rule)
        })
    return jsonify({"ok": True, "routes": out})

@app.post("/api/rag/index")
def rag_index():
    # Protected
    auth_fail = auth_or_401()
    if auth_fail:
        return auth_fail

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    text = (data.get("text") or "").strip()
    source = (data.get("source") or "").strip() or "note"

    if not title or not text:
        return jsonify({"ok": False, "error": "title and text are required"}), 400

    doc_id = f"doc_{int(datetime.now(timezone.utc).timestamp()*1000):d}"
    _DOCS.append({
        "id": doc_id,
        "title": title,
        "preview": text[:120],
        "source": source,
        "bow": _bow(text),
        "text": text,
    })
    return jsonify({"ok": True, "indexed": doc_id, "title": title, "chars": len(text)})

@app.post("/api/rag/query")
def rag_query():
    # Protected
    auth_fail = auth_or_401()
    if auth_fail:
        return auth_fail

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    topk = int(data.get("topk") or 3)

    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    qbow = _bow(query)
    scored = []
    for d in _DOCS:
        scored.append({
            "id": d["id"],
            "title": d["title"],
            "preview": d["preview"],
            "score": round(_cosine_sim(qbow, d["bow"]), 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    contexts = scored[:max(1, topk)]
    answer = " | ".join(c["title"] + " " + c["preview"] for c in contexts) or "No matches."
    return jsonify({"ok": True, "answer": f"Top {len(contexts)} matches -> {answer}", "contexts": contexts})

# -------------------------------------------------------------------
# Main (Render supplies PORT)
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Local dev: python app.py
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.getenv("DEBUG")))





















































