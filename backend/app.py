from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

ALLOWED = [
    "http://localhost:5173",
    "https://friday-full-bundle.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Optional convenience for any older UI bits that may hit /health
@app.get("/health")
async def root_health():
    return {"status": "ok"}








