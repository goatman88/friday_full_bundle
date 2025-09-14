# src/app.py
import os
import json
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask, jsonify, request, abort
from flask_cors import CORS

from openai_client import make_openai_client

# -------------------------------------------------------------------
# App & config
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

API_TOKEN = os.getenv("API_TOKEN", "")

# OpenAI client (proxy-safe)
oai = make_openai_client()

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def bearer_required():
    """Simple Bearer token gate for POST endpoints."""
    auth = request.headers.get("Authorization", "")
    if not API_TOKEN:
        return  # no auth required if not configured
    if not auth.startswith("Bearer "):
        abort(401)
    token = auth.split(" ", 1)[1]
    if token != API_TOKEN:
        abort(403)

def routes_list() -> List[str]:
    return [r.rule for r in app.url_map.iter_rules()]

def llm_embed(text: str) -> List[float]:
    """Create embeddings (OpenAI v1)."""
    resp = oai.embeddings.create(
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        input=text
    )
    return resp.data[0].embedding

def llm_answer(prompt: str) -> str:
    """Simple answer using responses API to avoid model drift across SDKs."""
    model = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    resp = oai.responses.create(
        model=model,
        input=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_output_tokens=256,
    )
    # responses API returns a structured message; extract text
    for item in resp.output_text.split("\n"):
        pass
    return resp.output_text.strip()

# -------------------------------------------------------------------
# In-memory toy store (kept so your existing smoke tests still pass)
# Replace with DB/pgvector later; schema was added in previous steps.
# -------------------------------------------------------------------
DOCUMENTS: List[Dict[str, Any]] = []

# -------------------------------------------------------------------
# Basic routes (used by your smoke tests)
# -------------------------------------------------------------------
@app.get("/")
def root():
    return jsonify({
        "message": "Friday backend is running",
        "ok": True,
        "routes": routes_list()
    })

@app.get("/__routes")
def __routes():
    return jsonify(routes_list())

@app.get("/__whoami")
def __whoami():
    return jsonify({
        "app_id": int(datetime.utcnow().timestamp() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip() or "unknown"
    })

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

@app.get("/ping")
def ping():
    return jsonify({"pong": True, "ts": datetime.utcnow().isoformat()})

# -------------------------------------------------------------------
# RAG endpoints (compatible with your PowerShell tests)
# -------------------------------------------------------------------
@app.post("/api/rag/index")
def rag_index():
    bearer_required()
    data = request.get_json(force=True, silent=True) or {}
    title = str(data.get("title") or "")
    text  = str(data.get("text") or "")
    source = str(data.get("source") or "unknown")
    mime = str(data.get("mime") or "text/plain")
    user_id = str(data.get("user_id") or "public")

    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400

    try:
        embedding = llm_embed(text)
        doc_id = f"doc_{len(DOCUMENTS)+1}"
        DOCUMENTS.append({
            "id": doc_id,
            "title": title,
            "preview": (text[:160] + "…") if len(text) > 160 else text,
            "text": text,
            "source": source,
            "mime": mime,
            "user_id": user_id,
            "embedding": embedding,
        })
        return jsonify({"ok": True, "indexed": True, "doc": {"id": doc_id, "title": title}})
    except Exception as e:
        return jsonify({"ok": False, "error": f"embed_failed: {e}"}), 500

@app.post("/api/rag/query")
def rag_query():
    bearer_required()
    data = request.get_json(force=True, silent=True) or {}
    query = str(data.get("query") or "")
    topk = int(data.get("topk") or 3)

    if not query:
        return jsonify({"ok": False, "error": "query required"}), 400

    # very simple retrieval: cosine via dot product on normalized vectors
    try:
        qv = llm_embed(query)
        def score(doc):
            # dot product (vectors are unit-normalized by OpenAI)
            return sum(a*b for a, b in zip(doc["embedding"], qv))
        ranked = sorted(DOCUMENTS, key=score, reverse=True)[:topk]
        context = "\n\n".join(f"- {d['title']}: {d['preview']}" for d in ranked)
        answer = llm_answer(f"Use the context to answer.\n\nContext:\n{context}\n\nQ: {query}\nA:")

        return jsonify({
            "ok": True,
            "answer": answer,
            "contexts": [
                {"id": d["id"], "preview": d["preview"], "title": d["title"], "score": None}
                for d in ranked
            ],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"query_failed: {e}"}), 500

@app.post("/api/rag/query-advanced")
def rag_query_advanced():
    """Placeholder for future advanced pipeline; kept to unblock your tests."""
    return rag_query()

# -------------------------------------------------------------------
# Entrypoint for waitress-serve: app:app
# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))




































































