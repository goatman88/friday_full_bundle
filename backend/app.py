from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/api/health")
def health():
    return {"status": "ok"}

class AskIn(BaseModel):
    q: str

@app.post("/api/ask")
def ask(body: AskIn):
    return {"answer": f"you asked: {body.q}"}




















