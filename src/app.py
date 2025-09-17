from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional
import time

app = FastAPI(title="Friday RAG API", version="0.1.0")

# ---------- Models ----------
class ConfirmUploadReq(BaseModel):
    s3_uri: str
    title: Optional[str] = None
    external_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunk: Optional[Dict[str, int]] = None
    source: Optional[str] = "cli"

class QueryReq(BaseModel):
    q: str

# ---------- Handlers ----------
def health_handler():
    return {"status": "ok", "ts": int(time.time()), "indexed": 0}

def confirm_upload_handler(_: ConfirmUploadReq):
    # pretend we queued indexing; return a simple receipt
    return {"ok": True, "received": True}

def query_handler(body: QueryReq):
    # dummy answer so the route exists
    return {"answer": f"Echo: {body.q}"}

# ---------- Mount the same routes on BOTH root and /api ----------
def mount(prefix: str = ""):
    base = FastAPI()

    @base.get(f"{prefix}/health")
    def health():
        return health_handler()

    @base.post(f"{prefix}/rag/confirm_upload")
    def confirm_upload(payload: ConfirmUploadReq):
        return confirm_upload_handler(payload)

    @base.post(f"{prefix}/rag/query")
    def query(payload: QueryReq):
        return query_handler(payload)

    return base

# expose at root
root = mount(prefix="")
app.mount("", root)

# and also expose under /api
api = mount(prefix="/api")
app.mount("/api", api)


# ----- Health ----------------------------------------------------------------
@app.get("/api/health")
def api_health():
    return {"status": "ok", "ts": int(time.time()), "indexed": 0}

# ----- RAG: confirm/index -----------------------------------------------------
@app.post("/api/rag/confirm_upload")
def confirm_upload(payload: ConfirmUploadReq):
    return {
        "ok": True,
        "message": "confirm_upload route is live",
        "received": payload.dict()
    }

# ----- RAG: query -------------------------------------------------------------
@app.post("/api/rag/query")
def rag_query(payload: QueryReq):
    return {
        "ok": True,
        "message": "query route is live",
        "echo": payload.q
    }

# ----- Root (optional) --------------------------------------------------------
@app.get("/")
def root():
    return {"status": "root-ok", "docs": "/docs"}

app = Flask(__name__)

# ----------------------------
# Health check route
# ----------------------------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ----------------------------
# RAG: confirm upload route
# ----------------------------
@app.route("/api/rag/confirm_upload", methods=["POST"])
def confirm_upload():
    data = request.get_json(silent=True) or {}
    return jsonify({
        "message": "confirm upload works",
        "received": data
    }), 200


# ----------------------------
# RAG: query route
# ----------------------------
@app.route("/api/rag/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    # Example: echo back the query text
    query_text = data.get("q", "No query provided")
    return jsonify({
        "message": "query works",
        "query_received": query_text
    }), 200


# ----------------------------
# Root route (optional)
# ----------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "Friday backend is live"}), 200


# ----------------------------
# Run locally
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)






















































































