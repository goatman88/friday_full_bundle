from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

# ---- CORS ----
ALLOWED_ORIGINS = [
    "http://localhost:5173",                     # local dev
    "https://friday-full-bundle.onrender.com",   # your deployed frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# (Optional safety net) Handle any stray OPTIONS so preflight never 404s
@app.options("/{path:path}")
async def any_options(path: str, request: Request):
    # Let CORSMiddleware attach the proper CORS headers;
    # just return an empty 204 body.
    return JSONResponse(status_code=204, content=None)

# ---- API ----
@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/ping")
async def ping():
    return {"message": "pong"}






