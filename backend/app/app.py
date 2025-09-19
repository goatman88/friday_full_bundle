from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Friday API", root_path="/api")

# Allow local dev + deployed frontend
frontend_origin = os.getenv("FRONTEND_ORIGIN")  # optional convenience
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if frontend_origin:
    origins.append(frontend_origin)

app.add_middleware(
    CORSOMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

