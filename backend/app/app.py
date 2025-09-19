from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Friday API", root_path="/api")

# Allow the Vite/frontend to call us
frontend_origin = os.getenv("FRONTEND_ORIGIN")  # optional
origins = [frontend_origin] if frontend_origin else [
    "http://localhost:5173", "http://127.0.0.1:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# sample route you can call from UI later
@app.get("/rag/query")
def rag_query(q: str):
    return {"answer": f"You asked: {q}"}

