from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.history import router as history_router
from backend.sse import router as sse_router
from backend.ws_chat import router as ws_router
from backend.stt_tts import router as speech_router
from backend.ask import router as ask_router
from backend.realtime_proxy import router as rt_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173","*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_root(): return {"status":"ok"}

@app.get("/api/health")
def health_api(): return {"status":"ok"}

app.include_router(history_router)
app.include_router(sse_router)
app.include_router(ws_router)
app.include_router(speech_router)
app.include_router(ask_router)        # /api/ask
app.include_router(rt_router)         # /api/realtime/sdp

