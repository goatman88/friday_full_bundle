from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

app = FastAPI(title="Friday API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def root_health():
    return {"status": "ok"}

api = APIRouter(prefix="/api")

@api.get("/health")
def api_health():
    return {"status": "ok"}

app.include_router(api)

from fastapi import UploadFile, File
import openai

@app.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    transcript = openai.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=("input.wav", audio_bytes, "audio/wav")
    )
    return {"text": transcript.text}

@app.post("/api/tts")
async def text_to_speech(text: str):
    response = openai.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    )
    return StreamingResponse(io.BytesIO(response.read()), media_type="audio/mpeg")


