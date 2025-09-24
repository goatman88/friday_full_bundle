# backend/app.py
import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

# ---------- Config (env overrides allowed) ----------
DEFAULT_TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")
DEFAULT_REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12")
DEFAULT_REALTIME_VOICE = os.getenv("REALTIME_VOICE", "verse")
APP_NAME = os.getenv("APP_NAME", "Friday Backend")

app = FastAPI(title=APP_NAME)
api = APIRouter(prefix="/api")

# ---------- Schemas ----------
class AskIn(BaseModel):
    q: str  # keep 'q' (PowerShell examples use this)

class AskOut(BaseModel):
    answer: str

class SessionOut(BaseModel):
    session_id: str
    models: Dict[str, Any]

# ---------- Health ----------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@api.get("/health")
def health_api():
    return {"status": "ok"}

# ---------- Simple ask (echo) ----------
@api.post("/ask", response_model=AskOut)
def ask(payload: AskIn):
    # Phase 1: simple “echo” so we can prove the pipe is good
    return AskOut(answer=f"You asked: {payload.q}")

# ---------- Realtime "session" stub ----------
@api.post("/session", response_model=SessionOut)
def session_create():
    # Phase 1: mint a local stub session id; wire real signaling in Phase 2
    sid = "local-dev-session"
    return SessionOut(
        session_id=sid,
        models={
            "text_model": DEFAULT_TEXT_MODEL,
            "realtime_model": DEFAULT_REALTIME_MODEL,
            "realtime_voice": DEFAULT_REALTIME_VOICE,
        },
    )

# mount router
app.include_router(api)













