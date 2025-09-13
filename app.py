import os
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from flask import Flask, jsonify, request, abort

# ------------------------------------------------------------------------------
# App bootstrap
# ------------------------------------------------------------------------------
app = Flask(__name__)

# In-memory "RAG" store (simple demo so we don't need any extra deps)
DOCUMENTS: List[Dict[str, Any]] = []

API_TOKEN = os.getenv("API_TOKEN", "").strip()  # set on Render
# Key presence is just a health signal; use whatever env var you actually have
AI_KEYS = [
    os.getenv("OPENAI_API_KEY", "").strip(),
    os.getenv("AI_API_KEY", "").strip(),
    os.getenv("OPENAI_KEY", "").strip(),
]
KEY_PRESENT = any(AI_KEYS)


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_auth():
    """Abort with 401 unless Authorization: Bearer <API_TOKEN> matches."""
    if not API_TOKEN:
        # If you forgot to set API_TOKEN in Render, make that obvious.
        abort(jsonify({"ok": False, "error": "Server missing API_TOKEN"}), 500)

    auth = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not auth.startswith(prefix):
        abort(jsonify({"ok": False, "error": "Unauthorized"}), 401)

    token = auth[len(prefix):].strip()
    if token != API_TOKEN:
        abort(jsonify({"ok": False, "error": "Unauthorized"}), 401)


def list_routes() -> List[Dict[str, Any]]:
    """Return a compact listing of public routes for debugging."""
    out = []
    for rule in app.url_map.iter_rules():
        # hide Flask internals
        if rule.endpoint == "static":
            continue
        out.append(
            {
                "endpoint": rule.endpoint,
                "rule": str(rule),
                "methods": sorted(m for m in rule.methods if m in {"GET", "POST"}),
            }
        )
    # stable sort for nicer diffs
    out.sort(key=lambda r: (r["endpoint"], r["rule"]))
    return out


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@app.get("/")
def home():
    return jsonify(
        {
            "ok": True,
            "message": "Friday backend is running",
            "docs": {
                "health": "/health",
                "routes": "/__routes (requires Authorization header)",
                "index": "/api/rag/index  (POST, requires Authorization)",
                "query": "/api/rag/query  (POST, requires Authorization)",
            },
        }
    )


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "status": "running",
            "time": now_iso(),
            "key_present": bool(KEY_PRESENT),
            "docs_indexed": len(DOCUMENTS),
        }
    )


@app.get("/__routes")
def routes():
    require_auth()
    return jsonify({"ok": True, "routes": list_routes()})


@app.post("/api/rag/index")
def rag_index():
    """
    Body JSON:
      { "title": "Widget FAQ", "text": "Widgets are blue...", "source": "faq" }
    """
    require_auth()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    text = (data.get("text") or "").strip()
    source = (data.get("source") or "").strip()

    if not title or not text:
        return jsonify({"ok": False, "error": "title and text are required"}), 400

    doc_id = f"doc_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    preview = text[:160]
    DOCUMENTS.append(
        {
            "id": doc_id,
            "title": title,
            "text": text,
            "preview": preview,
            "source": source or "unspecified",
        }
    )
    return jsonify({"ok": True, "indexed": doc_id, "title": title, "chars": len(text)})


@app.post("/api/rag/query")
def rag_query():
    """
    Body JSON:
      { "query": "What color are widgets?", "top_k": 3 }
    This is a tiny demo scorer (keyword/substring). Replace with your real RAG later.
    """
    require_auth()
    data = request.get_json(silent=True) or {}

    query = (data.get("query") or "").strip().lower()
    top_k = int(data.get("top_k") or 3)
    top_k = max(1, min(10, top_k))

    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    scored: List[Dict[str, Any]] = []
    for d in DOCUMENTS:
        txt = f"{d['title']} {d['text']}".lower()
        score = 0.0
        # very basic scoring: count query token appearances
        for token in query.split():
            if token and token in txt:
                score += 1.0
        # slight boost if substring match
        if query in txt:
            score += 1.5
        scored.append({"doc": d, "score": score})

    # sort by score desc, keep top_k
    scored.sort(key=lambda s: s["score"], reverse=True)
    top = [s for s in scored[:top_k] if s["score"] > 0.0]

    contexts = [
        {
            "id": s["doc"]["id"],
            "title": s["doc"]["title"],
            "preview": s["doc"]["preview"],
            "score": round(float(s["score"]), 4),
        }
        for s in top
    ]

    if contexts:
        # toy "answer"
        answer = "Top {} matches → ".format(len(contexts)) + " | ".join(
            c["preview"] for c in contexts
        )
    else:
        answer = "No matches found."

    return jsonify({"ok": True, "answer": answer, "contexts": contexts})

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Render supplies PORT; locally we default to 5000
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.getenv("FLASK_DEBUG")))





















































