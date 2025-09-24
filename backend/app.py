# app.py - single-file FastAPI backend (health, ask, session)
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

# -------- Health ----------
@app.get("/health")
def root_health():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

# -------- Models ----------
class AskIn(BaseModel):
    q: str

class AskOut(BaseModel):
    answer: str

# -------- Routes ----------
@api.post("/ask", response_model=AskOut)
def ask(payload: AskIn):
    # Echo-style stub. Replace with your LLM call later.
    return AskOut(answer=f"You asked: {payload.q}")

@api.post("/session")
def new_session():
    # Simple stub for Phase-2 (WebRTC etc. can hook here later)
    return {"session_id": "local-dev", "models": {"voice": ["alloy"], "realtime": ["gpt-realtime"]}}

app.include_router(api)














