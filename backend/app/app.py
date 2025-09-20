from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# IMPORTANT: root_path="/api" means every route below is served under /api
app = FastAPI(title="Friday API", root_path="/api")

# CORS (allow your Render static site + local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # or ["https://<your-static>.onrender.com", "http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# sample route the UI might call later
@app.get("/rag/query")
def rag_query(q: str):
    return {"answer": f"You asked: {q}"}

# optional: a friendly root message at /api
@app.get("/")
def root():
    return {"ok": True, "message": "Friday backend is running"}


