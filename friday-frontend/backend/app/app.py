from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Friday Backend")

# CORS — allow localhost:5173 for dev, and Render host if set
allowed = os.getenv("ALLOWED_ORIGINS", "")
origins = [o.strip() for o in allowed.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# Example POST you can wire up later
from pydantic import BaseModel
class AskIn(BaseModel):
    q: str

@app.post("/api/ask")
def ask(in_: AskIn):
    # placeholder answer so wiring works
    return {"answer": f"You asked: {in_.q}"}
