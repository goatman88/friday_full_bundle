import os, io
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- /api/stt: webm/ogg/wav -> text
@router.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Whisper via OpenAI
        r = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.webm", content)
        )
        return {"text": r.text}
    except Exception as e:
        raise HTTPException(400, str(e))

# --- /api/tts: text -> audio/mp3
@router.post("/api/tts")
async def tts(payload: dict):
    text = payload.get("text") or ""
    if not text:
        raise HTTPException(400, "text required")
    try:
        # choose your TTS model/voice
        audio = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text
        )
        # stream mp3 bytes out
        buf = io.BytesIO(audio.read())
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(400, str(e))

