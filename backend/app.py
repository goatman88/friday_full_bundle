# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI()

# Allow your Render frontend (and localhost for dev)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
# You can also allow multiple origins:
allow_origins = [FRONTEND_ORIGIN, "http://localhost:5173", "https://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,   # put your frontend URL here
    allow_credentials=True,
    allow_methods=["*"],           # needed so OPTIONS preflight succeeds
    allow_headers=["*"],           # needed so OPTIONS preflight succeeds
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

class AskBody(BaseModel):
    q: str

@app.post("/api/ask")
def ask(body: AskBody):
    return {"answer": f"you asked: {body.q}"}

