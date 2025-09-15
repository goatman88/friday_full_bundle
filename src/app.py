# src/app.py
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from openai import OpenAI
    client = OpenAI()  # no proxies kw
except Exception as e:
    # If the SDK import fails, surface it clearly at /health
    OpenAI = None
    _openai_import_error = e
else:
    _openai_import_error = None

app = Flask(__name__)
CORS(app, supports_credentials=True)

# ---- tiny helpers ----
def routes_list():
    return ["/", "/__routes", "/__whoami", "/health", "/ping",
            "/api/rag/index", "/api/rag/query"]

def _whoami():
    return {
        "app_id": os.getpid(),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": f"Python {os.sys.version.split()[0]}",
    }

def get_openai_client():
    """
    Construct OpenAI client lazily and safely.
    IMPORTANT: No 'proxies' kwarg; we let the SDK handle env automatically.
    """
    if OpenAI is None:
        raise RuntimeError(f"openai import error: {_openai_import_error!r}")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    # Do NOT pass proxies=... here.
    return OpenAI(api_key=api_key)

# ---- basic routes ----
@app.get("/")
def root():
    return jsonify({
        "message": "Friday backend is running",
        "ok": True,
        "routes": routes_list(),
    })

@app.get("/__routes")
def __routes():
    return jsonify(routes_list())

@app.get("/__whoami")
def whoami():
    return jsonify(_whoami())

@app.get("/health")
def health():
    if _openai_import_error:
        return jsonify({"ok": False, "status": "import_error", "error": str(_openai_import_error)}), 500
    return jsonify({"ok": True, "status": "running"})

@app.get("/ping")
def ping():
    return jsonify({"pong": True})

# ---- RAG (stubbed; your real impl can drop in here) ----
# POST /api/rag/index  {title, text, source, mime?, user_id?}
@app.post("/api/rag/index")
def rag_index():
    payload = request.get_json(force=True, silent=True) or {}
    # TODO: persist to Postgres/pgvector (your existing code can live here)
    return jsonify({"ok": True, "indexed": {k: payload.get(k) for k in ("title","source")}})

# POST /api/rag/query  {query, topk?}
@app.post("/api/rag/query")
def rag_query():
    payload = request.get_json(force=True, silent=True) or {}
    q = payload.get("query", "")
    topk = int(payload.get("topk", 3))
    # Example call that proves OpenAI is usable, but is not required:
    # client = get_openai_client()
    # _ = client.responses.create(model="gpt-4.1-mini", input=f"Echo: {q}")
    return jsonify({"ok": True, "answer": f"(stub) you asked: {q}", "topk": topk})

# WSGI entrypoint
def create_app():
    return app












































































