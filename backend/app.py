# backend/app.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

app = FastAPI()

# Render frontend URL and local dev URL:
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://friday-full-bundle.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Optional demo POST
@app.post("/api/ask")
async def ask(payload: dict):
    q = payload.get("q", "")
    return {"echo": q or "(empty)"}

# Safety: handle stray preflights (some proxies can 404 OPTIONS)
@app.options("/{full_path:path}")
async def any_options(full_path: str, request: Request):
    # CORS middleware will inject the proper Access-Control-* headers.
    return Response(status_code=204)







