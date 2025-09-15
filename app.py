import os
from datetime import datetime
from typing import List, Dict, Any
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from openai_client import make_openai_client

app = Flask(__name__)
CORS(app)
API_TOKEN = os.getenv("API_TOKEN", "")

# Create client once, with the safe factory (no proxies kw)
oai = make_openai_client()

def routes_list() -> List[str]:
    return [r.rule for r in app.url_map.iter_rules()]

def bearer_required():
    if not API_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401)
    if auth.split(" ", 1)[1] != API_TOKEN:
        abort(403)

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

_DB: List[Dict[str, Any]] = []

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))







































































