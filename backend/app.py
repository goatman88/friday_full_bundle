# backend/app.py
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday Backend", version="1.0.0")

# allow local vite + your Render origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*"  # relax for now; tighten later
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

class AskIn(BaseModel):
    # IMPORTANT: the UI and tests should send {"q": "..."}  (not "prompt")
    q: str

class AskOut(BaseModel):
    answer: str

@api.post("/ask", response_model=AskOut)
def ask(payload: AskIn):
    # simple echo for now; replace with OpenAI call later
    return AskOut(answer=f"You asked: {payload.q}")

app.include_router(api)








