import os
import base64
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# ------------ Env & defaults ------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "verse")  # e.g., alloy, verse, aria

# ------------ FastAPI app ------------
app = FastAPI(title="Friday Backend", version="1.0.0")

# CORS: allow local dev + render apps
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
for v in ("FRONTEND_ORIGIN", "FRONTEND_ORIGIN_2"):
    val = os.getenv(v)
    if val:
        origins.append(val)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")

# ------------ Schemas ------------
class AskIn(BaseModel):
    q: str

class AskOut(BaseModel):
    answer: str

class SessionIn(BaseModel):
    # optional client hints you may send
    device: Optional[str] = None
    user: Optional[str] = None

class SessionOut(BaseModel):
    session_id: str
    text_model: str
    realtime_model: str
    realtime_voice: str

class SDPIn(BaseModel):
    sdp: str
    # Optional: pass model/voice to override defaults
    model: Optional[str] = None
    voice: Optional[str] = None

class SDPOut(BaseModel):
    answer: str

# ------------ Health ------------
@app.get("/health")
def root_health() -> Dict[str, str]:
    return {"status": "ok"}

@api.get("/health")
def api_health() -> Dict[str, str]:
    return {"status": "ok"}

# ------------ /api/ask ------------
@api.post("/ask", response_model=AskOut)
async def ask(body: AskIn) -> AskOut:
    """
    If OPENAI_API_KEY is set, call OpenAI for a short answer.
    Otherwise, echo to prove the wiring works.
    """
    q = body.q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty question")

    if not OPENAI_API_KEY:
        return AskOut(answer=f"You asked: {q}")

    # Minimal OpenAI call using responses API (streaming not required for backend test)
    url = "https://api.openai.com/v1/responses"
    payload = {
        "model": TEXT_MODEL,
        "input": f"Answer briefly and clearly:\n\n{q}",
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"OpenAI error: {r.text}")
        data = r.json()
        # The 'output_text' helper exists in SDK; in raw REST, use .output[0].content[0].text
        try:
            answer = data["output"][0]["content"][0]["text"]
        except Exception:
            # Fallback if response shape changes
            answer = json.dumps(data)[:500]
    return AskOut(answer=answer)

# ------------ /api/session ------------
@api.post("/session", response_model=SessionOut)
async def session(_body: SessionIn) -> SessionOut:
    """
    Lightweight ephemeral session stub that returns the models & voice
    you configured. Your front-end uses this to decide which realtime
    params to send.
    """
    # You could mint a signed token here if you have your own auth.
    sid = base64.urlsafe_b64encode(os.urandom(9)).decode("utf-8").rstrip("=")
    return SessionOut(
        session_id=f"local-{sid}",
        text_model=TEXT_MODEL,
        realtime_model=REALTIME_MODEL,
        realtime_voice=REALTIME_VOICE,
    )

# ------------ /api/sdp (secure SDP proxy) ------------
@api.post("/sdp", response_model=SDPOut)
async def sdp_proxy(
    body: SDPIn,
    x_forwarded_for: Optional[str] = Header(None),
) -> SDPOut:
    """
    POST an SDP offer and have the server perform the server-to-server
    authenticated call to OpenAI Realtime.
    This keeps your API key off the client.
    """
    if not OPENAI_API_KEY:
        # Still return 200 with a helpful message so the UI can surface it.
        return SDPOut(answer="Server missing OPENAI_API_KEY; cannot open realtime session.")

    model = body.model or REALTIME_MODEL
    voice = body.voice or REALTIME_VOICE

    url = "https://api.openai.com/v1/realtime/sdp"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",           # OpenAI expects raw SDP
        "X-Requested-Model": model,
        "X-Requested-Voice": voice,
    }

    # body.sdp is a string; send it as the raw request body
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(url, headers=headers, content=body.sdp.encode("utf-8"))
        if r.status_code >= 400:
            # Return the reason to the client (do not leak key; we don't)
            raise HTTPException(status_code=500, detail=f"Realtime error: {r.text}")

        # OpenAI returns an SDP answer (string). We’ll Base64 it so the client
        # can carry it safely even if transport is JSON.
        answer_sdp = r.text
    return SDPOut(answer=answer_sdp)

# Mount router
app.include_router(api)











