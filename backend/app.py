from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow your local and Render frontends
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://friday-full-bundle.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/ask")
async def ask(payload: dict):
    q = (payload or {}).get("question", "")
    return {"you_asked": q, "answer": "42"}







