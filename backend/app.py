# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskBody(BaseModel):
    q: str

@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

@app.post("/api/ask")
def ask(body: AskBody):
    return {"answer": f"You asked: {body.q}"}

@app.post("/api/session")
def session():
    return {"session_id": "local-dev", "models": {"voice": "verse", "text": "gpt-mock"}}
















