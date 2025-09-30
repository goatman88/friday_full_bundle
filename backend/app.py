from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend to call backend
origins = [
    "http://localhost:5173",  # local dev
    "https://friday-full-bundle.onrender.com",  # deployed frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # frontend URLs allowed
    allow_credentials=True,
    allow_methods=["*"],            # allow all HTTP methods
    allow_headers=["*"],            # allow all headers
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/ping")
async def ping():
    return {"message": "pong"}



