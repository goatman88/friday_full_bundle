from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

app = FastAPI(title="Friday API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def root_health():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

app.include_router(api)



