from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow local + Render frontend
origins = [
    "http://localhost:5173",                  # local dev
    "https://friday-full-bundle.onrender.com" # Render frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/ask")
async def ask(payload: dict):
    question = payload.get("q", "")
    return {"answer": f"You asked: {question}"}


