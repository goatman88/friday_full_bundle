from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

# CORS for local dev + Render static site
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
    # dummy echo handler – replace with your real logic later
    return {"answer": f"You asked: {body.q}"}

@app.post("/api/session")
def session():
    # minimal phase-2 placeholder
    return {
        "id": "local",
        "models": {"voice": "avery", "text": "gpt-4o-mini"},
        "apiBase": "http://localhost:8000",
    }

















