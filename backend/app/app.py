import base64
import io
import os
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import redis
from pydub import AudioSegment

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

rds: Optional[redis.Redis] = None
try:
    rds = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    rds = None  # allow backend to run without Redis

app = FastAPI()

origins = [
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", "").strip(),  # allow your deployed FE if set
    "https://friday-099e.onrender.com",     # your Render backend (safe for CORS)
]
origins = [o for o in origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ["*"],  # dev-friendly; tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- health ----------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------- memory (Redis) ----------
class MemoryItem(BaseModel):
    key: str
    value: str

@app.post("/api/memory/set")
def memory_set(item: MemoryItem):
    if not rds:
        return {"ok": False, "error": "redis not configured"}
    rds.set(item.key, item.value)
    return {"ok": True}

@app.get("/api/memory/get")
def memory_get(key: str):
    if not rds:
        return {"ok": False, "error": "redis not configured"}
    val = rds.get(key)
    return {"ok": True, "value": val}

# ---------- LLM (stream-friendly, but also works non-stream) ----------
class AskIn(BaseModel):
    q: str
    system: Optional[str] = "You are a helpful assistant."

@app.post("/api/ask")
async def ask(in_: AskIn):
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}
    payload = {
        "model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": in_.system},
            {"role": "user", "content": in_.q},
        ],
        "temperature": float(os.getenv("OPENAI_TEMP", "0.2")),
        "stream": False
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    answer = data["choices"][0]["message"]["content"]
    return {"answer": answer}

# ---------- Vision (URL or upload) ----------
class VisionIn(BaseModel):
    prompt: str
    image_url: Optional[str] = None  # if not provided, use file upload

@app.post("/api/vision")
async def vision(prompt: str = Form(...), file: UploadFile = File(None), image_url: str = Form(None)):
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}

    content: List = [{"type": "text", "text": prompt}]

    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    elif file is not None:
        bytes_ = await file.read()
        b64 = base64.b64encode(bytes_).decode("utf-8")
        # send as data URL (png assumed; OpenAI supports base64 for vision)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    else:
        return {"error": "Provide image_url or file"}

    payload = {
        "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENAI_BASE}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    answer = data["choices"][0]["message"]["content"]
    return {"answer": answer}

# ---------- STT (speech -> text) ----------
@app.post("/api/stt")
async def stt(audio: UploadFile = File(...)):
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}

    # OpenAI's Whisper endpoint expects multipart form
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    form = {
        "model": "whisper-1",
    }
    files = {"file": (audio.filename, await audio.read(), audio.content_type or "audio/wav")}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENAI_BASE}/audio/transcriptions", headers=headers, data=form, files=files)
        resp.raise_for_status()
        data = resp.json()
    return {"text": data.get("text", "")}

# ---------- TTS (text -> audio) ----------
class TTSIn(BaseModel):
    text: str
    voice: Optional[str] = "alloy"  # depends on model support

@app.post("/api/tts")
async def tts(in_: TTSIn):
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set"}

    # OpenAI speech synthesis returns bytes; we’ll return wav in base64
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        "voice": in_.voice,
        "input": in_.text,
        "format": "wav"
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENAI_BASE}/audio/speech", json=payload, headers=headers)
        resp.raise_for_status()
        audio_bytes = resp.content

    # Ensure WAV container
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
    buf = io.BytesIO()
    seg.export(buf, format="wav")
    wav_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {"audio_wav_b64": wav_b64}




