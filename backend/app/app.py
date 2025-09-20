from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Friday API")

# --- CORS (safe + simple) ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")  # e.g. https://friday_full_bundle.onrender.com
allow_origins = [FRONTEND_ORIGIN] if FRONTEND_ORIGIN else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health (NOTE: under /api) ---
@app.get("/api/health")
def health():
    return {"status": "ok"}

# (You can add more API routes under /api/... later)




