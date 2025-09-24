# backend/app.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# -----------------------------------------------------------------------------
# App + CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="Friday Backend", version="2.0.0")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://localhost:5173",
    os.getenv("FRONTEND_ORIGIN", "").strip(),
]
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def root_health():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class AskBody(BaseModel):
    q: str
    latency: Optional[str] = None  # "fast" | "quality" (hint)

class AskResult(BaseModel):
    answer: str

class SessionInfo(BaseModel):
    session_id: str
    text_model: str
    realtime_model: str
    realtime_voice: str
    # For direct WebRTC (browser -> OpenAI) you'll use this:
    webrtc_url: str
    # For browser that talks via our proxy (optional):
    sdp_proxy_url: str
    # Ephemeral token (short-lived) that the browser uses for WebRTC auth:
    client_secret: Optional[str] = None

class SDPBody(BaseModel):
    sdp: str
    model: Optional[str] = None
    voice: Optional[str] = None

# -----------------------------------------------------------------------------
# OpenAI settings
# -----------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

TEXT_MODEL      = os.getenv("TEXT_MODEL",      "gpt-4o-mini")
REALTIME_MODEL  = os.getenv("REALTIME_MODEL",  "gpt-4o-realtime-preview")
REALTIME_VOICE  = os.getenv("REALTIME_VOICE",  "verse")

# Official endpoints
OPENAI_BASE            = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
REALTIME_WEBRTC_URL    = f"{OPENAI_BASE}/realtime?model={REALTIME_MODEL}"
REALTIME_SESSION_URL   = f"{OPENAI_BASE}/realtime/sessions"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _choose_text_model(latency_hint: Optional[str]) -> str:
    if latency_hint == "quality":
        # swap to a bigger model if you like, env override allowed
        return os.getenv("TEXT_MODEL_QUALITY", TEXT_MODEL)
    return os.getenv("TEXT_MODEL_FAST", TEXT_MODEL)

# -----------------------------------------------------------------------------
# /api/ask -> OpenAI text (fallback to echo if no key set)
# -----------------------------------------------------------------------------
@api.post("/ask", response_model=AskResult)
async def api_ask(body: AskBody) -> Dict[str, Any]:
    q = body.q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="q is required")

    # If no key yet, keep Phase-1 behavior so dev doesn’t break
    if not OPENAI_API_KEY:
        return {"answer": f"You asked: {q}"}

    model = _choose_text_model(body.latency)

    # Call Chat Completions (stable for gpt-4o-mini)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{OPENAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are Friday, a concise helpful assistant."},
                        {"role": "user", "content": q},
                    ],
                    "temperature": 0.3,
                },
            )
            r.raise_for_status()
            data = r.json()
            answer = data["choices"][0]["message"]["content"]
            return {"answer": answer}
    except httpx.HTTPError as e:
        # degrade gracefully
        return {"answer": f"(fallback) You asked: {q} — upstream error: {e}"}

# -----------------------------------------------------------------------------
# /api/session -> mint ephemeral token for WebRTC + return model/voice
# -----------------------------------------------------------------------------
@api.get("/session", response_model=SessionInfo)
async def api_session():
    # Default response: no token, but still provide URLs & models (useful in dev)
    client_secret: Optional[str] = None

    if OPENAI_API_KEY:
        # Create a one-time short-lived client_secret for WebRTC
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    REALTIME_SESSION_URL,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": REALTIME_MODEL,
                        "voice": REALTIME_VOICE,
                        # session expires quickly; it is intentionally ephemeral
                        "expiration": 60,  # seconds (adjust to taste)
                    },
                )
                r.raise_for_status()
                client_secret = r.json().get("client_secret", {}).get("value")
        except httpx.HTTPError:
            # Keep going without a token so the UI can still render
            client_secret = None

    return SessionInfo(
        session_id="local-dev",
        text_model=TEXT_MODEL,
        realtime_model=REALTIME_MODEL,
        realtime_voice=REALTIME_VOICE,
        webrtc_url=REALTIME_WEBRTC_URL,     # for direct browser->OpenAI WebRTC
        sdp_proxy_url="/realtime/sdp",      # our backend SDP proxy
        client_secret=client_secret,
    )

# -----------------------------------------------------------------------------
# /realtime/sdp (SDP offer->answer proxy) for WebRTC setups that
# want the server in the middle instead of hitting OpenAI directly.
# -----------------------------------------------------------------------------
@api.post("/sdp")
async def realtime_sdp(body: SDPBody):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set on the server")

    model = (body.model or REALTIME_MODEL).strip()
    voice = (body.voice or REALTIME_VOICE).strip()
    sdp   = body.sdp

    url = f"{OPENAI_BASE}/realtime?model={model}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/sdp",
                    # Optional: instruct voice at session start
                    "OpenAI-Beta-Voice": voice,
                },
                content=sdp.encode("utf-8"),
            )
            r.raise_for_status()
            # Pass the SDP answer straight through
            return Response(content=r.text, media_type="application/sdp")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Realtime upstream error: {e}") from e

# mount router
app.include_router(api)









