from flask import Flask, request, jsonify
# src/app.py
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Any, Dict
import time

app = FastAPI(title="Friday RAG API", version="0.1.0")

# ----- Models (minimal) -------------------------------------------------------
class ConfirmUploadReq(BaseModel):
    s3_uri: str | None = None
    title: str | None = None
    external_id: str | None = None
    metadata: Dict[str, Any] | None = None
    chunk: Dict[str, Any] | None = None
    source: str | None = None

class QueryReq(BaseModel):
    q: str

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






















































































