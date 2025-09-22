from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, List
import os, json, asyncio
import redis.asyncio as redis
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

rdb = redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI()

# CORS
origins = [
    "http://localhost:5173",
    "https://localhost:5173",
    os.getenv("CORS_ORIGIN", "")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------- Health ----------
@app.get("/health")
async def health_root():
    return {"status":"ok"}

@app.get("/api/health")
async def health_api():
    return {"status":"ok"}

# ---------- History in Redis ----------
def _k(session_id:str): return f"session:{session_id}:messages"

@app.get("/api/history/{session_id}")
async def get_history(session_id:str):
    items = await rdb.lrange(_k(session_id), 0, -1)
    return [json.loads(x) for x in items]

class MessageIn(BaseModel):
    role: str
    content: str

@app.post("/api/history/{session_id}")
async def push_message(session_id:str, msg:MessageIn):
    await rdb.rpush(_k(session_id), json.dumps(msg.model_dump()))
    return {"ok": True}

# ---------- SSE Streaming (server -> browser) ----------
class AskIn(BaseModel):
    q: str
    session: str | None = None

async def _sse_stream(question:str, session:str|None) -> AsyncGenerator[bytes, None]:
    # pull history from redis (optional)
    history = []
    if session:
        items = await rdb.lrange(_k(session), 0, -1)
        history = [json.loads(x) for x in items]

    msgs: List[Dict] = [{"role":"system","content":"You are Friday, concise and helpful."}]
    msgs += history
    msgs.append({"role":"user","content":question})

    # store the new user message
    if session:
        await rdb.rpush(_k(session), json.dumps({"role":"user","content":question}))

    # stream tokens
    stream = await client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        stream=True,
    )
    full_text = ""
    yield b"retry: 1000\n"  # SSE hint
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            full_text += delta
            payload = f"data: {json.dumps({'delta': delta})}\n\n"
            yield payload.encode("utf-8")

    # store assistant message
    if session:
        await rdb.rpush(_k(session), json.dumps({"role":"assistant","content":full_text}))
    yield b"data: [DONE]\n\n"

@app.post("/api/ask/stream")
async def ask_stream(body: AskIn):
    return StreamingResponse(_sse_stream(body.q, body.session), media_type="text/event-stream")

# ---------- WebSocket Chat (bi-directional) ----------
@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            question = data.get("q","")
            session = data.get("session")

            # stream via OpenAI; aggregate and forward chunks
            msgs = [{"role":"system","content":"You are Friday, concise and helpful."}]
            if session:
                items = await rdb.lrange(_k(session), 0, -1)
                msgs += [json.loads(x) for x in items]
                await rdb.rpush(_k(session), json.dumps({"role":"user","content":question}))
            msgs.append({"role":"user","content":question})

            stream = await client.chat.completions.create(
                model=MODEL, messages=msgs, stream=True
            )
            full=""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full += delta
                    await ws.send_text(json.dumps({"delta": delta}))
            if session:
                await rdb.rpush(_k(session), json.dumps({"role":"assistant","content":full}))
            await ws.send_text(json.dumps({"done": True}))
    except WebSocketDisconnect:
        return









