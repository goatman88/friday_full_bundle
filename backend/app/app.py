from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

app = FastAPI(title="Friday API")

# CORS (permits all while you debug; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /health at root
@app.get("/health")
def root_health():
    return {"status": "ok"}

# /api/health via sub-router
api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

app.include_router(api)
