from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API", root_path="/api")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://friday-frontend.onrender.com",  # <-- replace with your actual static site URL after first deploy
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

