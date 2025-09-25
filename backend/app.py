import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday Backend")

# CORS for local Vite and Render/static
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*",  # loosen during dev; tighten in prod
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

class AskIn(BaseModel):
    q: str

@app.post("/api/ask")
def ask(payload: AskIn):
    q = payload.q.strip()
    if not q:
        return {"answer": "(empty question)"}
    # stubbed reply until Phase 2 model integration
    return {"answer": f"You asked: {q}"}

@app.post("/api/session")
def session():
    # simple stub; in Phase 2 we’ll return real model/voice ids, etc.
    return {
        "id": "local-session",
        "models": {"voice": "none", "text": "none"},
    }



















