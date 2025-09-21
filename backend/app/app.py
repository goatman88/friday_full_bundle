# backend/app/app.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

# allow local dev + your deployed frontend (tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        # "https://<YOUR-STATIC-FRONTEND-DOMAIN>"  # uncomment+set when you deploy the frontend
    ],
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


