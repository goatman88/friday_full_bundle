# backend/app.py
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

@app.get("/health")
def root_health():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

class AskIn(BaseModel):
    prompt: str

@api.get("/health")
def api_health():
    return {"status": "ok"}

@api.post("/ask")
def ask(body: AskIn):
    # Phase-1 stub: just echoes; wire to OpenAI later
    return {"you_sent": body.prompt}

app.include_router(api)







