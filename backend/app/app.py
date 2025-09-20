from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Everything below will be served under /api
app = FastAPI(title="Friday API", root_path="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# simple root to help debug
@app.get("/")
def root():
    return {"ok": True, "message": "Friday backend live"}

# optional: a quick echo endpoint
@app.get("/rag/query")
def rag_query(q: str):
    return {"answer": f"You asked: {q}"}



