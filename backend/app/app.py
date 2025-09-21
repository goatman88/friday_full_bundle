# backend/app/app.py
import io
import os
import base64
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from dotenv import load_dotenv

# --- OpenAI (v1.x SDK) ---
# pip install openai>=1.40.0
from openai import OpenAI

# ------------------------------------------------------------------
# Boot
# ------------------------------------------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Friday Backend")

# CORS: allow your Vite dev server and Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in prod if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}

# ------------------------------------------------------------------
# STT (Speech → Text)
# Accepts .webm/.m4a/.wav — MediaRecorder webm recommended.
# ------------------------------------------------------------------
@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Missing OPENAI_API_KEY"}, status_code=500)

    audio_bytes = await file.read()

    # OpenAI SDK accepts tuple (filename, bytes, mimetype)
    # Model: gpt-4o-mini-transcribe (or 'whisper-1' if you prefer)
    tr = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=("input.webm", audio_bytes, file.content_type or "audio/webm"),
    )
    return {"text": tr.text}

# ------------------------------------------------------------------
# TTS (Text → Speech)
# Returns audio/mpeg stream; voices: alloy, verse, breeze, etc.
# ------------------------------------------------------------------
@app.post("/api/tts")
async def tts(
    text: str = Form(...),
    voice: str = Form("alloy"),
    speed: Optional[float] = Form(1.0),
):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Missing OPENAI_API_KEY"}, status_code=500)

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        speed=speed,
        format="mp3",
    )

    return StreamingResponse(io.BytesIO(speech.read()), media_type="audio/mpeg")

# ------------------------------------------------------------------
# Ask (LLM text response) — useful after STT to get an answer
# ------------------------------------------------------------------
@app.post("/api/ask")
async def ask(prompt: str = Form(...), system: str = Form("You are Friday, a helpful assistant.")):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Missing OPENAI_API_KEY"}, status_code=500)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return {"text": resp.choices[0].message.content}

# ------------------------------------------------------------------
# Vision (Image → Description)
# Send an image, returns a description (and accepts an optional prompt)
# ------------------------------------------------------------------
@app.post("/api/vision")
async def vision(
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image succinctly, then list 3 notable details.")
):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "Missing OPENAI_API_KEY"}, status_code=500)

    img_bytes = await file.read()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    data_url = f"data:{file.content_type or 'image/jpeg'};base64,{b64}"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.3,
    )
    return {"description": resp.choices[0].message.content}


