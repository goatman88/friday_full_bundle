# backend/app.py
import os
import json
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .redis_store import (
    create_session, append_message, get_messages, push_wake, pop_wake
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gpt-4o")
REALTIME_MODEL = os.environ.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE = os.environ.get("REALTIME_VOICE", "verse")
CORS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if CORS == ["*"] else CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Health ----------------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------------- Session ----------------
@app.get("/session")
async def get_session():
    sid = str(uuid.uuid4())
    await create_session(sid)
    return {
        "session_id": sid,
        "realtime": {"model": REALTIME_MODEL, "voice": REALTIME_VOICE},
        "text_model": TEXT_MODEL,
    }

# ---------------- /api/ask ----------------
@app.post("/api/ask")
async def ask(request: Request):
    body = await request.json()
    q = (body.get("q") or "").strip()
    if not q:
        raise HTTPException(400, "Missing 'q'")

    session_id: Optional[str] = body.get("session_id")
    latency = (body.get("latency") or "").strip().lower()

    text_model = TEXT_MODEL
    if latency == "balanced":
        text_model = "gpt-4o-mini"
    elif latency == "ultra":
        text_model = "gpt-4o-mini"

    msgs = [
        {"role": "system", "content": "You are a concise, helpful assistant."},
        {"role": "user", "content": q},
    ]

    if session_id:
        await append_message(session_id, "user", q)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {"model": text_model, "messages": msgs, "temperature": 0.3}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        answer = data["choices"][0]["message"]["content"]
        if session_id:
            await append_message(session_id, "assistant", answer)
        return {"answer": answer}

# ---------------- Realtime SDP proxy ----------------
@app.post("/realtime/sdp", response_class=PlainTextResponse)
async def sdp_proxy(request: Request):
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    q = dict(request.query_params)
    latency = q.get("latency", "").lower()

    model = REALTIME_MODEL
    if latency == "balanced":
        model = "gpt-4o-realtime-preview"
    elif latency == "ultra":
        model = "gpt-4o-realtime-preview-lite"

    sdp_text = body.decode("utf-8")
    if "application/json" in content_type:
        try:
            sdp_text = json.loads(sdp_text)["sdp"]
        except Exception:
            raise HTTPException(400, "Invalid JSON offer")

    openai_url = f"https://api.openai.com/v1/realtime?model={model}&voice={REALTIME_VOICE}"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/sdp"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(openai_url, headers=headers, content=sdp_text)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        return Response(content=r.text, media_type="application/sdp")

# ---------------- Ephemeral token (Direct Realtime) ----------------
@app.post("/ephemeral")
async def ephemeral_token(request: Request):
    """
    Returns a one-minute client token for direct WebRTC (browser -> OpenAI).
    Do NOT expose your permanent key in the browser.
    """
    body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    latency = (body.get("latency") or "").lower()

    model = REALTIME_MODEL
    if latency == "balanced":
        model = "gpt-4o-realtime-preview"
    elif latency == "ultra":
        model = "gpt-4o-realtime-preview-lite"

    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "voice": REALTIME_VOICE,
        "ttl": 60,  # seconds
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        # OpenAI returns: { "client_secret": { "value": "ephemeral-..." }, ... }
        try:
            token = data["client_secret"]["value"]
        except Exception:
            raise HTTPException(500, "Unexpected token response")
        return {"ephemeral_token": token}

# ---------------- Wake trigger endpoints ----------------
@app.post("/wake")
async def wake_post():
    await push_wake()
    return {"ok": True}

@app.get("/wake/next")
async def wake_next():
    """Long-poll for a wake signal; returns {wake:true} or {wake:false}."""
    item = await pop_wake(timeout_sec=25)
    return {"wake": bool(item)}



