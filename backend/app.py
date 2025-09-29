from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="Friday Backend", version="0.1.0")

# ----- CORS -----
# In dev we allow all (Vite runs on 5173). In prod, set FRONTEND_ORIGIN env var on Render.
frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
origins = [frontend_origin] if frontend_origin != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Routes -----
@app.get("/api/health")
def health():
    return {"status": "ok"}

class AskBody(BaseModel):
    q: str

@app.post("/api/ask")
def ask(body: AskBody):
    # Placeholder logic; later we’ll call OpenAI here.
    q = body.q.strip()
    if not q:
        return {"answer": "Please ask a question."}
    return {"answer": f"You asked: {q}"}
