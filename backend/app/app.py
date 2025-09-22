from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import AsyncGenerator, List, Dict, Any
import asyncio, os, io, base64
from PIL import Image
import redis.asyncio as redis
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

app = FastAPI(title="Friday Backend")

# --- CORS (local dev + your Render domain allowed) ---
FRONTEND = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
origins = [FRONTEND, "http://localhost:5173", "https://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Redis connection (optional) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client: redis.Redis | None = None
try:
    redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
except Exception:
    redis_client = None

# --- OpenAI client (streaming) ---
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# -------- Conversation store helpers (Redis) ----------
async def save_message(session_id: str, role: str, content: str) -> None:
    if not redis_client: return
    await redis_client.rpush(f"chat:{session_id}", f"{role}:{content}")

async def load_messages(session_id: str, limit: int = 50) -> List[Dict[str, str]]:
    if not redis_client: return []
    items = await redis_client.lrange(f"chat:{session_id}", -limit, -1)
    msgs = []
    for it in items:
        role, content = it.split(":", 1)
        msgs.append({"role": role, "content": content})
    return msgs

# -------- Basic ask (non-stream) ----------
class AskIn(BaseModel):
    q: str
    session_id: str | None = None

@app.post("/api/ask")
async def ask(in_: AskIn):
    session = in_.session_id or "default"
    await save_message(session, "user", in_.q)

    msgs = [{"role": "system", "content": "You are Friday."}]
    msgs += await load_messages(session)
    msgs.append({"role": "user", "content": in_.q})

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=msgs,
        stream=False,
    )
    answer = resp.choices[0].message.content
    await save_message(session, "assistant", answer)
    return {"answer": answer}

# -------- SSE streaming ----------
@app.get("/api/stream")
async def stream(q: str, session_id: str | None = None):
    session = session_id or "default"

    async def event_gen() -> AsyncGenerator[str, None]:
        await save_message(session, "user", q)
        msgs = [{"role": "system", "content": "You are Friday."}]
        msgs += await load_messages(session)
        msgs.append({"role": "user", "content": q})

        stream = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=msgs, stream=True
        )

        chunks = []
        async for part in stream:
            delta = part.choices[0].delta.content or ""
            if delta:
                chunks.append(delta)
                yield f"data: {delta}\n\n"
                await asyncio.sleep(0)  # keep loop cooperative

        full = "".join(chunks)
        await save_message(session, "assistant", full)
        yield "event: done\ndata: [DONE]\n\n"

    return EventSourceResponse(event_gen())

# -------- WebSocket streaming ----------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            q = data.get("q", "")
            session = data.get("session_id", "default")
            await save_message(session, "user", q)

            msgs = [{"role": "system", "content": "You are Friday."}]
            msgs += await load_messages(session)
            msgs.append({"role": "user", "content": q})

            stream = await client.chat.completions.create(
                model=OPENAI_MODEL, messages=msgs, stream=True
            )
            chunks = []
            async for part in stream:
                delta = part.choices[0].delta.content or ""
                if delta:
                    chunks.append(delta)
                    await ws.send_text(delta)
            full = "".join(chunks)
            await save_message(session, "assistant", full)
            await ws.send_json({"done": True})
    except WebSocketDisconnect:
        return

# -------- Vision (image + prompt) ----------
@app.post("/api/vision")
async def vision(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    session_id: str = Form("default"),
):
    img_bytes = await image.read()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{image.content_type};base64,{b64}"}}
    ]

    msgs = [{"role": "user", "content": content}]
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", messages=msgs
    )
    ans = resp.choices[0].message.content
    await save_message(session_id, "assistant", ans)
    return {"answer": ans}

# -------- STT (upload audio -> text) ----------
@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    # passthrough to Whisper via OpenAI API (using "audio.transcriptions")
    audio_bytes = await file.read()
    resp = await client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=("speech.wav", audio_bytes, file.content_type or "audio/wav"),
    )
    return {"text": resp.text}

# -------- TTS (text -> wav) ----------
class TTSIn(BaseModel):
    text: str

@app.post("/api/tts")
async def tts(in_: TTSIn):
    # text to speech via OpenAI (audio.speech)
    audio = await client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=in_.text,
        format="wav",
    )
    return StreamingResponse(io.BytesIO(audio.read()), media_type="audio/wav")







