# backend/app/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

# Allow your static site to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Health at root
@app.get("/health")
def root_health():
    return {"status": "ok"}

# ✅ Health under /api
@app.get("/api/health")
def api_health():
    return {"status": "ok"}







