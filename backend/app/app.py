from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

# Allow Vite dev + your Render domain later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api
@app.get("/api/health")
def health():
    return {"ok": True}

# --- Demo endpoints (you can replace with your real ones later) ---

@app.post("/api/rag/upload_url")
def get_upload_url():
    # Normally you'd mint a presigned URL; for now just say "ok"
    return {"upload_url": "/api/rag/upload"}  # dummy local endpoint

@app.put("/api/rag/confirm_upload")
def confirm_upload():
    return {"ok": True}

@app.post("/api/rag/query")
def rag_query(top_k: int = 5, index: str = "both"):
    # Replace with your retrieval logic later
    return {"answer": f"Demo answer (top_k={top_k}, index={index})"}

