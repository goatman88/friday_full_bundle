# backend/app.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="Friday Backend")

# CORS: allow local dev frontend and Render frontends
allowed = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in allowed.split(",")] if allowed else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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

# ---------- Simple /api/ask stub (works now; you can swap in OpenAI later) ----------
class AskIn(BaseModel):
    prompt: str
    latency: str | None = "fast"

class AskOut(BaseModel):
    answer: str
    meta: dict

@api.post("/ask", response_model=AskOut)
def api_ask(body: AskIn):
    # For now we just echo to prove wiring; you can replace this with real LLM logic.
    return AskOut(
        answer=f"You asked: {body.prompt}",
        meta={"latency": body.latency or "fast", "engine": "stub"},
    )

# ---------- Session stub so the frontend/tests don’t 404 ----------
class SessionOut(BaseModel):
    client_secret: str
    model: str

@api.post("/session", response_model=SessionOut)
def api_session():
    # In a real setup, return a signed ephemeral token for the Realtime API
    return SessionOut(client_secret="dev-stub-token", model=os.getenv("REALTIME_MODEL", "gpt-realtime-preview"))

app.include_router(api)

if __name__ == "__main__":
    # allow `python backend/app.py` if you ever want that
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)






