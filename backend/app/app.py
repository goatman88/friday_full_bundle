from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API", root_path="/api")

# Allow the Vite dev server
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
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

# ---- example endpoints the UI might call ----
# (leave in place even if unused for now)
@app.get("/rag/query")
def rag_query(q: str):
    return {"answer": f"You asked: {q}"}
