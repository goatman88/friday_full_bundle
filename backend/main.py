from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
import os

app = FastAPI()
api = APIRouter(prefix="/api")

# Models
class AskRequest(BaseModel):
    prompt: str

# Health checks
@app.get("/health")
def root_health():
    return {"status": "ok"}

@api.get("/health")
def api_health():
    return {"status": "ok"}

# Ask endpoint
@api.post("/ask")
def ask(req: AskRequest):
    return {"you_asked": req.prompt}

# Session endpoint (placeholder for realtime use)
@api.post("/session")
def session():
    return {
        "session_id": "local-dev",
        "realtime_model": os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview"),
        "voice": os.getenv("REALTIME_VOICE", "verse"),
    }

app.include_router(api)


