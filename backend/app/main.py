from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio, os, base64, json
from typing import AsyncGenerator, Optional, List
from redis.asyncio import Redis
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ALLOW_ORIGINS  = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
MODEL          = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Redis connection
redis: Optional[Redis] = None
@app.on_event("startup")
async def startup():
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if redis:
        await redis.close()

# --- Schemas
class AskBody(BaseModel):
    session_id: str
    message: str
    image_data_url: Optional[str] = None   # optional base64 from <canvas>

# --- Health
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# --- History (Redis list per session)
@app.get("/api/history/{session_id}")
async def get_history(session_id: str) -> List[dict]:
    key = f"hist:{session_id}"
    raw = await redis.lrange(key, 0, -1)
    return [json.loads(x) for x in raw]

async def _save_turn(session_id: str, role: str, content: dict):
    key = f"hist:{session_id}"
    await redis.rpush(key, json.dumps({"role": role, "content": content}))
    await redis.expire(key, 60 * 60 * 24 * 7)  # 7d TTL

# --- OpenAI client
oai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Helper to build messages from history + latest user message
async def build_messages(session_id: str, user_text: str, image_data_url: Optional[str]):
    hist = await get_history(session_id)
    msgs = [{"role": h["role"], "content": h["content"]["text"]} for h in hist if "text" in h["content"]]
    content = user_text
    if image_data_url:
        # Pass as text note—replace with Vision if you want real image understanding
        content += "\n[Attached image data-url received]"
    msgs.append({"role": "user", "content": content})
    return msgs

# --- /api/ask (non-stream)
@app.post("/api/ask")
async def ask(body: AskBody):
    await _save_turn(body.session_id, "user", {"text": body.message})
    msgs = await build_messages(body.session_id, body.message, body.image_data_url)
    resp = await oai.chat.completions.create(
        model=MODEL,
        messages=msgs
    )
    answer = resp.choices[0].message.content
    await _save_turn(body.session_id, "assistant", {"text": answer})
    return {"answer": answer}

# --- SSE streamer
@app.post("/api/stream")
async def sse_stream(body: AskBody):
    await _save_turn(body.session_id, "user", {"text": body.message})
    msgs = await build_messages(body.session_id, body.message, body.image_data_url)

    async def _gen() -> AsyncGenerator[bytes, None]:
        yield b"event: status\ndata: starting\n\n"
        stream = await oai.chat.completions.create(
            model=MODEL, messages=msgs, stream=True
        )
        full = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full.append(delta)
                yield f"data: {delta}\n\n".encode("utf-8")
        text = "".join(full)
        await _save_turn(body.session_id, "assistant", {"text": text})
        yield b"event: done\ndata: end\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")

# --- WebSocket streamer
@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    try:
        payload = await ws.receive_json()
        session_id = payload.get("session_id", "default")
        message = payload.get("message", "")
        await _save_turn(session_id, "user", {"text": message})
        msgs = await build_messages(session_id, message, None)

        stream = await oai.chat.completions.create(
            model=MODEL, messages=msgs, stream=True
        )
        full = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full.append(delta)
                await ws.send_text(delta)
        await _save_turn(session_id, "assistant", {"text": "".join(full)})
        await ws.send_json({"event": "done"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_json({"event": "error", "detail": str(e)})
    finally:
        await ws.close()

# --- Image upload (optional; you can keep data-url on /api/ask instead)
@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...), session_id: str = Form(...)):
    b = await file.read()
    b64 = base64.b64encode(b).decode("utf-8")
    await _save_turn(session_id, "user", {"image_b64": b64, "mime": file.content_type})
    return {"ok": True}











