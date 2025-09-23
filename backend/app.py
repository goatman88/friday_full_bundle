# backend/app.py
import os
import json
import uuid
from typing import Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gpt-4o")
REALTIME_MODEL = os.environ.get("REALTIME_MODEL", "gpt-4o-realtime-preview")
REALTIME_VOICE = os.environ.get("REALTIME_VOICE", "alloy")

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set")

app = FastAPI()

# CORS
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- tiny in-memory session store (dev) ---
SESSIONS: Dict[str, Dict[str, Any]] = {}

# ---------- Health ----------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------- Session ----------
@app.get("/session")
def get_session():
    """Create and return a short-lived session id & the model/voice the server prefers."""
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {"messages": []}
    return {
        "session_id": sid,
        "realtime": {
            "model": REALTIME_MODEL,
            "voice": REALTIME_VOICE
        },
        "text_model": TEXT_MODEL
    }

# ---------- /api/ask (server text call to OpenAI) ----------
@app.post("/api/ask")
async def ask(request: Request):
    body = await request.json()
    question = (body.get("q") or "").strip()
    session_id = body.get("session_id")
    latency = (body.get("latency") or "").strip()  # "", "balanced", "ultra"
    if not question:
        raise HTTPException(400, "Missing 'q'")

    # Optional per-request latency profile
    text_model = TEXT_MODEL
    if latency == "balanced":
        text_model = "gpt-4o-mini"
    elif latency == "ultra":
        text_model = "gpt-4o-mini"

    messages = [
        {"role": "system", "content": "You are a concise helpful assistant."},
        {"role": "user", "content": question},
    ]

    # Keep dev history in memory
    if session_id and session_id in SESSIONS:
        SESSIONS[session_id]["messages"].extend(messages)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": text_model,
        "messages": messages,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = {"error": r.text}
            raise HTTPException(r.status_code, detail)
        data = r.json()
        answer = data["choices"][0]["message"]["content"]
        if session_id and session_id in SESSIONS:
            SESSIONS[session_id]["messages"].append({"role": "assistant", "content": answer})
        return {"answer": answer}

# ---------- Secure Realtime SDP proxy ----------
# Browser sends SDP offer; we forward to OpenAI; return OpenAI's SDP answer.
@app.post("/realtime/sdp", response_class=PlainTextResponse)
async def sdp_proxy(request: Request):
    """Proxies WebRTC SDP to OpenAI. Returns SDP answer as text/plain (application/sdp)."""
    # accept either JSON {sdp, mode} or raw SDP text; default Studio
    content_type = request.headers.get("content-type", "")
    body_text = await request.body()

    # Choose model by querystring (?latency=balanced|ultra)
    q = dict(request.query_params)
    latency = q.get("latency", "").lower()
    model = REALTIME_MODEL
    if latency == "balanced":
        model = "gpt-4o-realtime-preview"
    elif latency == "ultra":
        model = "gpt-4o-realtime-preview-lite"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",
    }

    # If client posted JSON, unwrap to the raw SDP
    sdp_text = body_text.decode("utf-8")
    if "application/json" in content_type:
        try:
            obj = json.loads(sdp_text)
            sdp_text = obj.get("sdp", "")
        except Exception:
            raise HTTPException(400, "Invalid JSON offer")

    openai_url = f"https://api.openai.com/v1/realtime?model={model}&voice={REALTIME_VOICE}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(openai_url, headers=headers, content=sdp_text)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        # OpenAI responds with 'application/sdp'
        return Response(content=r.text, media_type="application/sdp")


