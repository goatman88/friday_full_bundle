import asyncio, base64, io, json, os
from typing import AsyncGenerator, Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# --- env ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- optional redis ---
r = None
try:
    import redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
except Exception:
    r = None  # fall back to in-memory

# in-memory fallback (dev only)
MEMORY: Dict[str, List[Dict[str, Any]]] = {}

# --- openai client ---
from openai import OpenAI
oai = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Friday Backend")

# CORS for Vite dev and Render
origins = ["http://localhost:5173", "http://127.0.0.1:5173", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ---------- health ----------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------- models ----------
class AskIn(BaseModel):
    q: str
    session_id: Optional[str] = "default"

class VisionIn(BaseModel):
    session_id: Optional[str] = "default"
    prompt: str
    image_base64: str  # dataURL or pure base64

class HistoryIn(BaseModel):
    role: str
    content: str

# ---------- history helpers ----------
def _push_history(session_id: str, role: str, content: str):
    entry = {"role": role, "content": content}
    if r:
        r.rpush(session_id, json.dumps(entry))
    else:
        MEMORY.setdefault(session_id, []).append(entry)
    return entry

def _get_history(session_id: str) -> List[Dict[str, Any]]:
    if r:
        return [json.loads(x) for x in r.lrange(session_id, 0, -1)]
    return MEMORY.get(session_id, [])

def _clear_history(session_id: str):
    if r:
        r.delete(session_id)
    else:
        MEMORY.pop(session_id, None)

# ---------- simple /api/ask (non-stream) ----------
@app.post("/api/ask")
def ask(in_: AskIn):
    msgs = _get_history(in_.session_id) + [{"role": "user", "content": in_.q}]
    _push_history(in_.session_id, "user", in_.q)

    # Use chat.completions (most compatible)
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": m["role"], "content": m["content"]} for m in msgs],
        temperature=0.2,
    )
    answer = resp.choices[0].message.content
    _push_history(in_.session_id, "assistant", answer)
    return {"answer": answer}

# ---------- SSE streaming ----------
def sse(data: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")

@app.get("/api/stream")
def stream(q: str, session_id: str = "default"):
    async def gen() -> AsyncGenerator[bytes, None]:
        msgs = _get_history(session_id) + [{"role": "user", "content": q}]
        _push_history(session_id, "user", q)

        stream = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": m["role"], "content": m["content"]} for m in msgs],
            stream=True, temperature=0.2,
        )
        full = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full.append(delta)
                yield sse({"token": delta})
        answer = "".join(full)
        _push_history(session_id, "assistant", answer)
        yield sse({"done": True})

    return StreamingResponse(gen(), media_type="text/event-stream")

# ---------- history endpoints ----------
@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return _get_history(session_id)

@app.post("/api/history/{session_id}")
def post_history(session_id: str, entry: HistoryIn):
    return _push_history(session_id, entry.role, entry.content)

@app.delete("/api/history/{session_id}")
def delete_history(session_id: str):
    _clear_history(session_id)
    return {"deleted": True}

# ---------- simple vision endpoint (snapshot -> reasoning) ----------
@app.post("/api/vision")
def vision(in_: VisionIn):
    # accept data URLs or raw base64
    b64 = in_.image_base64
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]

    image_url = {"url": f"data:image/jpeg;base64,{b64}"}
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": in_.prompt},
            {"type": "input_image", "image_url": image_url["url"]},
        ]}
    ]
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )
    answer = resp.choices[0].message.content
    _push_history(in_.session_id, "user", f"[vision] {in_.prompt}")
    _push_history(in_.session_id, "assistant", answer)
    return {"answer": answer}

# ---------- WebSocket demo (text streaming) ----------
@app.websocket("/ws/ask")
async def ws_ask(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            q = await ws.receive_text()
            stream = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"user","content":q}],
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    await ws.send_text(delta)
                    await asyncio.sleep(0)
            await ws.send_text("[[DONE]]")
    except WebSocketDisconnect:
        pass

# ---------- WebSocket relay to OpenAI Realtime (skeleton) ----------
# You can connect your browser to ws://localhost:8000/ws/realtime
# and forward JSON/text frames to OpenAI realtime model.
import websockets

@app.websocket("/ws/realtime")
async def ws_realtime(ws: WebSocket):
    await ws.accept()
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
    try:
        async with websockets.connect(uri, extra_headers=headers) as upstream:
            async def down():
                async for m in upstream:
                    # forward (text/binary) back to browser
                    if isinstance(m, bytes):
                        await ws.send_bytes(m)
                    else:
                        await ws.send_text(m)

            async def up():
                while True:
                    msg = await ws.receive()
                    if "text" in msg:
                        await upstream.send(msg["text"])
                    elif "bytes" in msg:
                        await upstream.send(msg["bytes"])

            await asyncio.gather(up(), down())
    except Exception as e:
        await ws.send_text(json.dumps({"error": str(e)}))
        await ws.close()










