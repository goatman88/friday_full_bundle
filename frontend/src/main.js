# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

const BASE = import.meta.env.VITE_BACKEND_URL || '';
document.querySelector('#base').textContent = `Backend: ${BASE || '(not set)'}`;

async function hit(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

origins = [
    "http://localhost:5173",
    "https://friday-full-bundle.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/ask")
async def ask(payload: dict):
    q = (payload or {}).get("q", "")
    return {"answer": f"you asked: {q}"}





