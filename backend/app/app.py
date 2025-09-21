# backend/app/app.py
import io, os, base64, asyncio
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Friday Backend (Voice + Vision, Streaming TTS)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- health ----------
@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/api/health")
def api_health(): return {"status": "ok"}

def _require_key():
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Missing OPENAI_API_KEY"}, status_code=500)

# ---------- STT (speech -> text) ----------
@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    err = _require_key()
    if err: return err
    audio_bytes = await file.read()
    tr = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",  # or "whisper-1"
        file=("input.webm", audio_bytes, file.content_type or "audio/webm"),
    )
    return {"text": tr.text}

# ---------- LLM text answer ----------
@app.post("/api/ask")
async def ask(
    prompt: str = Form(...),
    system: str = Form("You are Friday, a concise, helpful assistant.")
):
    err = _require_key()
    if err: return err
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.4,
    )
    return {"text": r.choices[0].message.content}

# ---------- TTS (text -> speech, non-stream) ----------
@app.post("/api/tts")
async def tts(
    text: str = Form(...),
    voice: str = Form("alloy"),
    speed: Optional[float] = Form(1.0),
):
    err = _require_key()
    if err: return err
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts", voice=voice, input=text, speed=speed, format="mp3"
    )
    return StreamingResponse(io.BytesIO(speech.read()), media_type="audio/mpeg")

# ---------- TTS (text -> speech, STREAMING) ----------
@app.post("/api/tts/stream")
async def tts_stream(
    text: str = Form(...),
    voice: str = Form("alloy"),
    speed: Optional[float] = Form(1.0),
):
    err = _require_key()
    if err: return err

    stream = client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts", voice=voice, input=text, speed=speed, format="mp3"
    )

    async def gen():
        with stream as s:
            for chunk in s.iter_bytes(chunk_size=4096):
                yield chunk
                await asyncio.sleep(0)  # cooperate with loop

    return StreamingResponse(gen(), media_type="audio/mpeg")

# ---------- Vision (single or multi-image) ----------
@app.post("/api/vision")
async def vision(
    files: List[UploadFile] = File(...),
    prompt: str = Form("Describe the image(s) succinctly, then list notable details.")
):
    err = _require_key()
    if err: return err

    parts = [{"type":"text","text":prompt}]
    for f in files:
        b = await f.read()
        b64 = base64.b64encode(b).decode("utf-8")
        parts.append({
            "type":"image_url",
            "image_url":{"url": f"data:{f.content_type or 'image/jpeg'};base64,{b64}"}
        })

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":parts}],
        temperature=0.3,
    )
    return {"description": r.choices[0].message.content}



