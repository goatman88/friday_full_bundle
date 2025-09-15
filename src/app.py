import os
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

from .settings import FRIDAY_NAME, API_TOKEN, FRONTEND_ORIGIN, OPENAI_API_KEY, COMMIT_SHA

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": [FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else "*"}},
    supports_credentials=False,
)

# ---- OpenAI client (NO proxies kw) ----
# The SDK reads OPENAI_API_KEY from env automatically, but we pass it explicitly too.
_oai = OpenAI(api_key=OPENAI_API_KEY or None)

# ---- tiny in-memory index just for smoke tests ----
_INDEX = []  # each item: {id,title,text,source,mime,user_id,ts}

def _auth_ok(req: request) -> bool:
    """Optional Bearer token gate for mutating routes."""
    if not API_TOKEN:  # no token configured => allow
        return True
    header = req.headers.get("Authorization", "")
    return header == f"Bearer {API_TOKEN}"

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": f"{FRIDAY_NAME} backend is running",
        "ok": True,
        "routes": [r.rule for r in app.url_map.iter_rules()],
        "commit": COMMIT_SHA,
    })

@app.route("/__routes", methods=["GET"])
def list_routes():
    return jsonify([r.rule for r in app.url_map.iter_rules()])

@app.route("/__whoami", methods=["GET"])
def whoami():
    return jsonify({
        "app_id": int(time.time() * 1000),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip() or "unknown",
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "running", "commit": COMMIT_SHA})

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"pong": True, "ts": time.time()})

# ---- RAG-ish smoke routes ----

@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    if not _auth_ok(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    item = {
        "id": f"doc_{len(_INDEX)+1}",
        "title": data.get("title", "Untitled"),
        "text": data.get("text", ""),
        "source": data.get("source", "user"),
        "mime": data.get("mime", "text/plain"),
        "user_id": data.get("user_id", "public"),
        "ts": time.time(),
    }
    _INDEX.append(item)
    return jsonify({"ok": True, "indexed": True, "doc": {"id": item["id"], "title": item["title"]}})

@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    data = request.get_json(silent=True) or {}
    q = data.get("query", "")
    topk = int(data.get("topk", 3))

    # toy keyword rank
    scored = []
    for it in _INDEX:
        score = sum(1 for w in q.lower().split() if w in it["text"].lower())
        if score:
            scored.append((score, it))
    scored.sort(reverse=True, key=lambda x: x[0])
    ctx = [{"id": it["id"], "title": it["title"], "preview": it["text"][:120], "score": s} for s, it in scored[:topk]]

    # synth answer via OpenAI (optional)
    answer = ""
    if OPENAI_API_KEY and q:
        try:
            # tiny, safe completion
            prompt = f"Answer briefly:\nQ: {q}\nContext snippets:\n" + "\n".join(
                f"- {c['title']}: {c['preview']}" for c in ctx
            )
            chat = _oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150,
            )
            answer = (chat.choices[0].message.content or "").strip()
        except Exception as e:
            answer = f"(LLM unavailable: {e})"

    return jsonify({"ok": True, "answer": answer, "contexts": ctx})











































































