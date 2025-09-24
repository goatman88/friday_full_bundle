# backend/app.py
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = FastAPI(title="Friday Backend", version="1.0.0")

# Allow your Vite dev server and Render-hosted frontend
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://localhost:5173",
    os.getenv("FRONTEND_ORIGIN", ""),  # optional: e.g. https://friday-frontend-xxxx.onrender.com
]
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public health
@app.get("/health")
def root_health():
    return {"status": "ok"}

# Versioned API
api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class AskBody(BaseModel):
    q: str
    latency: Optional[str] = None   # "fast" | "quality" (optional hint used later)

class SessionInfo(BaseModel):
    session_id: str
    text_model: str
    realtime_model: str
    realtime_voice: str
    websocket_url: str

# -----------------------------------------------------------------------------
# /api/ask  (Phase 1: echo response; Phase 2 swaps in OpenAI call)
# -----------------------------------------------------------------------------
@api.post("/ask")
def api_ask(body: AskBody):
    # Phase-1 behavior is intentionally simple and predictable.
    # (We’ll swap the implementation to OpenAI in Phase-2, no frontend changes needed.)
    return {"answer": f"You asked: {body.q}"}

# -----------------------------------------------------------------------------
# /api/session  (pulled from main.py, normalized)
# Returns the realtime/text model + voice selection for the frontend.
# -----------------------------------------------------------------------------
@api.get("/session", response_model=SessionInfo)
def api_session():
    # Read from env with sensible defaults; these carry into Phase-2/3.
    text_model      = os.getenv("TEXT_MODEL",       "gpt-4o-mini")
    realtime_model  = os.getenv("REALTIME_MODEL",   "gpt-4o-realtime-preview")
    realtime_voice  = os.getenv("REALTIME_VOICE",   "verse")
    websocket_url   = os.getenv("WS_BASE",          "wss://api.openai.com/v1/realtime")  # placeholder; we’ll replace in Phase-2B

    # local-only, stable, no auth state here — it’s just a capability descriptor
    return SessionInfo(
        session_id="local-dev",
        text_model=text_model,
        realtime_model=realtime_model,
        realtime_voice=realtime_voice,
        websocket_url=websocket_url,
    )

# Register router
app.include_router(api)









