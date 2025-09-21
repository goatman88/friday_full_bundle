# backend/app/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

# CORS (keep permissive for now; restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health at /
@app.get("/health")
def root_health():
    return {"status": "ok"}

# Health under /api
@app.get("/api/health")
def api_health():
    return {"status": "ok"}
