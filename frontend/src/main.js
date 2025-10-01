# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

const BASE = import.meta.env.VITE_BACKEND_URL;
const out = document.querySelector("#out");
const btn = document.querySelector("#ping");

btn.addEventListener("click", async () => {
  out.textContent = "Loading…";
  try {
    const r = await fetch(`${BASE}/api/health`, { headers: { "Content-Type": "application/json" }});
    const j = await r.json();
    out.textContent = JSON.stringify(j);
  } catch (e) {
    out.textContent = "ERROR: " + (e?.message || e);
  }
});

// optional: show which base is baked in
const baseEl = document.querySelector("#base");
if (baseEl) baseEl.textContent = `BASE = ${BASE}`;


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





