import base64, io, os, json, asyncio
from typing import Optional, List, AsyncGenerator
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx, redis
from pydub import AudioSegment
from starlette.responses import StreamingResponse

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE    = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
CHAT_MODEL     = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
VISION_MODEL   = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
TTS_MODEL      = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TEMP           = float(os.getenv("OPENAI_TEMP", "0.2"))
REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    rds: Optional[redis.Redis] = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    rds = None

def mem_add(session_id: str, role: str, content: str):
    if not rds: return
    key = f"chat:{session_id}"
    rds.rpush(key, json.dumps({"role": role, "content": content}))
    rds.ltrim(key, -40, -1)  # keep last 40

def mem_get(session_id: str) -> List[dict]:
    if not rds: return []
    key = f"chat:{session_id}"
    vals = rds.lrange(key, 0, -1) or []
    return [json.loads(v) for v in vals]

app = FastAPI()
origins = [ "http://localhost:5173", os.getenv("FRONTEND_URL","").strip() ]
origins = [o for o in origins if o]
app.add_middleware(CORSMiddleware, allow_origins=origins+["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health_root(): return {"status": "ok"}

@app.get("/api/health")
def health_api(): return {"status": "ok"}

# ---------- standard chat ----------
class AskIn(BaseModel):
    q: str
    system: Optional[str] = "You are a helpful assistant."
    session_id: Optional[str] = "default"

@app.post("/api/ask")
async def ask(in_: AskIn):
    if not OPENAI_API_KEY: return {"error": "OPENAI_API_KEY not set"}
    history = mem_get(in_.session_id)
    messages = [{"role": "system", "content": in_.system}] + history + [{"role": "user", "content": in_.q}]
    payload = { "model": CHAT_MODEL, "messages": messages, "temperature": TEMP, "stream": False }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    answer = data["choices"][0]["message"]["content"]
    mem_add(in_.session_id, "user", in_.q)
    mem_add(in_.session_id, "assistant", answer)
    return {"answer": answer}

# ---------- SSE stream ----------
@app.get("/api/ask/stream")
async def ask_stream(q: str, session_id: str = "default", system: str = "You are a helpful assistant."):
    async def gen() -> AsyncGenerator[bytes, None]:
        if not OPENAI_API_KEY:
            yield b"data: ERROR: OPENAI_API_KEY not set\n\n"; return
        history = mem_get(session_id)
        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": q}]
        payload = { "model": CHAT_MODEL, "messages": messages, "temperature": TEMP, "stream": True }
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers) as r:
                async for line in r.aiter_lines():
                    if not line: continue
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            yield b"data: [DONE]\n\n"; break
                        try:
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield f"data: {delta}\n\n".encode("utf-8")
                        except Exception:
                            pass
        # store final turn (best-effort; client can also send a final text)
        # NOTE: you can collect on client and POST to /api/ask to store
    return StreamingResponse(gen(), media_type="text/event-stream")

# ---------- WebSocket stream ----------
@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()     # {q, session_id?, system?}
            q       = msg.get("q","")
            sid     = msg.get("session_id","default")
            system  = msg.get("system","You are a helpful assistant.")
            if not q:
                await ws.send_json({"error":"empty q"}); continue

            history = mem_get(sid)
            messages = [{"role":"system","content":system}] + history + [{"role":"user","content":q}]
            payload = {"model": CHAT_MODEL, "messages": messages, "temperature": TEMP, "stream": True}
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

            collected = []
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers) as r:
                    async for line in r.aiter_lines():
                        if not line: continue
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk == "[DONE]": break
                            try:
                                obj = json.loads(chunk)
                                delta = obj["choices"][0]["delta"].get("content","")
                                if delta:
                                    collected.append(delta)
                                    await ws.send_text(delta)
                            except: pass
            final = "".join(collected)
            mem_add(sid, "user", q); mem_add(sid, "assistant", final)
            await ws.send_json({"done": True})
    except WebSocketDisconnect:
        return

# ---------- Vision ----------
@app.post("/api/vision")
async def vision(prompt: str = Form(...), file: UploadFile = File(None), image_url: str = Form(None)):
    if not OPENAI_API_KEY: return {"error": "OPENAI_API_KEY not set"}
    content: List = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type":"image_url","image_url":{"url": image_url}})
    elif file:
        b64 = base64.b64encode(await file.read()).decode("utf-8")
        content.append({"type":"image_url","image_url":{"url": f"data:image/png;base64,{b64}"}})
    else:
        return {"error":"Provide image_url or file"}
    payload = {"model": VISION_MODEL, "messages":[{"role":"user","content": content}]}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers)
        r.raise_for_status(); data = r.json()
    return {"answer": data["choices"][0]["message"]["content"]}

# ---------- STT ----------
@app.post("/api/stt")
async def stt(audio: UploadFile = File(...)):
    if not OPENAI_API_KEY: return {"error":"OPENAI_API_KEY not set"}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {"file": (audio.filename, await audio.read(), audio.content_type or "audio/wav")}
    data  = {"model":"whisper-1"}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{OPENAI_BASE}/audio/transcriptions", headers=headers, data=data, files=files)
        r.raise_for_status(); j = r.json()
    return {"text": j.get("text","")}

# ---------- TTS ----------
class TTSIn(BaseModel):
    text: str
    voice: Optional[str] = "alloy"

@app.post("/api/tts")
async def tts(in_: TTSIn):
    if not OPENAI_API_KEY: return {"error":"OPENAI_API_KEY not set"}
    payload = {"model": TTS_MODEL, "voice": in_.voice, "input": in_.text, "format":"wav"}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{OPENAI_BASE}/audio/speech", json=payload, headers=headers)
        r.raise_for_status(); audio_bytes = r.content
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
    buf = io.BytesIO(); seg.export(buf, format="wav")
    return {"audio_wav_b64": base64.b64encode(buf.getvalue()).decode("utf-8")}





