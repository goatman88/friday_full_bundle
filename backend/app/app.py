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

@app.post("/api/vision")
async def vision(file: UploadFile = File(...)):
    image_bytes = await file.read()
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "Describe this image"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"}}
        ]}]
    )
    return {"description": response.choices[0].message["content"]}

