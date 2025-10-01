# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# ---- CORS config ----
# Primary production frontend on Render:
FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "https://friday-full-bundle.onrender.com",   # fallback
)

# Optional “allow all” override while debugging (set to "true" only temporarily)
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

if CORS_ALLOW_ALL:
    allow_origins = ["*"]
else:
    allow_origins = [
        FRONTEND_ORIGIN,           # deployed frontend
        "http://localhost:5173",   # local dev
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],  # includes Content-Type, etc.
)

# Catch-all OPTIONS handler (belt & suspenders in case a proxy eats headers)
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return {"ok": True}

# ---- Routes ----
@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/ping")
async def ping():
    return {"message": "pong"}





