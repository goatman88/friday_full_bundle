import os
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, APIRouter, Body, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# --- env ---
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "verse")

if not OPENAI_API_KEY:
    print("⚠️  OPENAI_API_KEY is not set. /api/ask will fall back to echo mode; /api/session and /api/sdp will 401.")

# --- app ---
app = FastAPI(title="Friday Backend")

# Allow your local Vite dev server and Render-hosted frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        os.getenv("FRONTEND_ORIGIN", "").strip() or "https://*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_root():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

@api.get("/health")
def health_api():
    return {"status": "ok"}

# ---------- /api/ask  ----------
class AskIn(BaseModel):
    q: str

class AskOut(BaseModel):
    answer: str

@api.post("/ask", response_model=AskOut)
async def ask_route(payload: AskIn):
    """
    Answers a text question. If OPENAI_API_KEY is set, calls the Responses API.
    Otherwise, returns a simple echo (useful for smoke tests).
    """
    q = payload.q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing 'q'")

    if not OPENAI_API_KEY:
        return AskOut(answer=f"You asked: {q}")

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body: Dict[str, Any] = {
        "model": TEXT_MODEL,
        "input": [
            {"role": "user", "content": q}
        ],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json()
        # Responses API returns aggregated text under output_text
        answer = data.get("output_text") or f"You asked: {q}"
        return AskOut(answer=answer)

# ---------- /api/session (Realtime ephemeral session) ----------
class SessionOut(BaseModel):
    # The OpenAI Realtime "client_secret" style payload (opaque to us)
    client_secret: Dict[str, Any]

@api.post("/session", response_model=SessionOut)
async def create_session():
    """
    Creates an ephemeral session for WebRTC or WebSocket Realtime clients.
    Frontend fetches this and gives it to the OpenAI Realtime client.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=401, detail="Server missing OPENAI_API_KEY")

    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": REALTIME_MODEL,
        "voice": REALTIME_VOICE,
        # optionally tune other settings here:
        # "input_audio_format": {"type": "wav"},
        # "turn_detection": {"type": "server_vad"},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

# ---------- /api/sdp (secure WebRTC SDP proxy) ----------
@api.post("/sdp")
async def sdp_proxy(request: Request):
    """
    Proxies a WebRTC SDP offer to OpenAI and returns the answer.
    Accepts 'application/sdp' or raw text body. Returns text/SDP.
    This keeps your API key on the server.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=401, detail="Server missing OPENAI_API_KEY")

    offer_sdp = await request.body()
    if not offer_sdp:
        raise HTTPException(status_code=400, detail="Missing SDP offer body")

    openai_url = f"https://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(openai_url, headers=headers, content=offer_sdp)
        if r.status_code >= 400:
            # Return underlying error from OpenAI (keep text to preserve SDP diagnostics)
            raise HTTPException(status_code=r.status_code, detail=r.text)

        # OpenAI returns an SDP answer as text/plain
        return Response(content=r.text, media_type="application/sdp")

# Mount router
app.include_router(api)










