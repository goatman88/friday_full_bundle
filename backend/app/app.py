# backend/app/app.py
import os
import json
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Redis (optional but recommended) ---
_redis = None
REDIS_URL = os.getenv("REDIS_URL")

try:
    if REDIS_URL:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    _redis = None

# --- OpenAI (optional streaming demo) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
try:
    if OPENAI_API_KEY:
        from openai import AsyncOpenAI
        oai = AsyncOpenAI(api_key=OPENAI_API_KEY)
    else:
        oai = None
except Exception:
    oai = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # warmup, ping redis if configured
    if _redis:
        try:
            await _redis.ping()
        except Exception:
            pass
    yield
    # teardown
    try:
        if _redis:
            await _redis.close()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)

# CORS for local dev + render
origins = [
    "http://localhost:5173",
    "https://localhost:5173",
]
if os.getenv("PUBLIC_FRONTEND_ORIGIN"):
    origins.append(os.getenv("PUBLIC_FRONTEND_ORIGIN"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ["*"],  # relax for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Health --------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# -------- Memory (Redis) helpers --------
async def append_history(session_id: str, role: str, content: str):
    if not _redis:
        return
    key = f"chat:{session_id}"
    await _redis.rpush(key, json.dumps({"role": role, "content": content}))
    # Keep last 100 msgs
    await _redis.ltrim(key, -100, -1)

async def get_history(session_id: str):
    if not _redis:
        return []
    key = f"chat:{session_id}"
    items = await _redis.lrange(key, 0, -1)
    return [json.loads(x) for x in items]

# -------- SSE streaming --------
class AskIn(BaseModel):
    q: str
    session_id: Optional[str] = "default"

@app.post("/api/ask")
async def ask(body: AskIn):
    # non-streaming basic echo until you wire OpenAI RAG
    await append_history(body.session_id, "user", body.q)
    text = f"You asked: {body.q}"
    await append_history(body.session_id, "assistant", text)
    return {"answer": text}

@app.post("/api/stream")
async def stream_answer(body: AskIn):
    async def gen():
        # Real model streaming (OpenAI) if configured; else fake chunks
        if oai:
            # lightweight streaming completion
            prompt = f"Answer briefly: {body.q}"
            stream = await oai.chat.completions.create(
                model="gpt-4o-mini",
                stream=True,
                messages=[{"role":"user","content":prompt}],
            )
            collected = []
            async for ev in stream:
                delta = ev.choices[0].delta.content or ""
                if delta:
                    collected.append(delta)
                    yield f"data: {delta}\n\n"
            final = "".join(collected)
            await append_history(body.session_id, "user", body.q)
            await append_history(body.session_id, "assistant", final)
            yield "event: done\ndata: [DONE]\n\n"
        else:
            # demo chunks
            for chunk in ["Thinking", " … ", "done."]:
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.3)
            yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

# -------- WebSocket streaming --------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            # Echo server; upgrade to model stream if desired
            await ws.send_text(f"server received: {msg}")
    except WebSocketDisconnect:
        pass

# -------- Simple vision stub (HTTP image upload) --------
from fastapi import UploadFile, File

@app.post("/api/vision/analyze")
async def analyze(file: UploadFile = File(...)):
    # replace with OpenAI vision call later
    content = await file.read()
    return {"ok": True, "bytes": len(content)}








