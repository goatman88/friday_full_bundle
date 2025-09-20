from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

# Allow the frontend (local dev & Render static site)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # you can add your Render static site URL here later if you want strict CORS
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

# example endpoint the UI might call
@app.get("/api/rag/query")
def rag_query(q: str):
    return {"answer": f"You asked: {q}"}





