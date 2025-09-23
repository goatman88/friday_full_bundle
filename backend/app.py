from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.history import router as history_router       # A
from backend.sse import router as sse_router               # B
from backend.ws_chat import router as ws_router            # C
from backend.stt_tts import router as speech_router        # E

app = FastAPI()

# Allow vite dev + any localhost callers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_root(): return {"status": "ok"}

@app.get("/api/health")
def health_api(): return {"status": "ok"}

# Mount feature routers
app.include_router(history_router)   # /api/history/:session
app.include_router(sse_router)       # /api/stream
app.include_router(ws_router)        # /ws/chat
app.include_router(speech_router)    # /api/stt, /api/tts
