# app.py
import os
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

APP_NAME = "Friday Backend"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "verse")
DEFAULT_LATENCY = os.getenv("DEFAULT_LATENCY", "fast")

app = FastAPI(title=APP_NAME)

# ----- Schemas -----
class AskIn(BaseModel):
    q: str
    latency: Optional[str] = DEFAULT_LATENCY

class AskOut(BaseModel):
    answer: str

class SessionOut(BaseModel):
    session_id: str
    text_model: str
    realtime_model: str
    realtime_voice: str
    latency: str

# ----- Routes -----
@app.get("/health")
def root_health():
    return {"status": "ok"}

from fastapi import APIRouter
api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

@api.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    # Phase 1: stubbed echo. (Phase 2 will call your model here.)
    return AskOut(answer=f"You asked: {body.q}")

@api.post("/session", response_model=SessionOut)
def session():
    # Phase 1: fixed values. (Phase 2 will mint a realtime token if needed.)
    return SessionOut(
        session_id="local-dev",
        text_model=TEXT_MODEL,
        realtime_model=REALTIME_MODEL,
        realtime_voice=REALTIME_VOICE,
        latency=DEFAULT_LATENCY,
    )

app.include_router(api)
