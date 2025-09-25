from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskIn(BaseModel):
    q: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/ask")
def ask(body: AskIn):
    return {"answer": f"You asked: {body.q}"}

@app.post("/api/session")
def session():
    return {
        "id": "local",
        "models": {"voice": "avery", "text": "gpt-4o-mini"},
        "apiBase": "http://localhost:8000",
    }
