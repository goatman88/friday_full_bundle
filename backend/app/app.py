from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:5173",
    "https://localhost:5173",
    # add your Render URL so dev can call prod:
    "https://friday-099e.onrender.com",  # <- replace with your real host if different
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
    # placeholder answer (replace with RAG/LLM later)
    return {"answer": f"You asked: {in_.q}"}






