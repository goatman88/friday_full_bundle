import os, io, time, json, queue, tempfile, numpy as np
import sounddevice as sd
import soundfile as sf
import requests

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BACKEND_BASE   = os.getenv("BACKEND_BASE", "http://localhost:8000")
SESSION_ID     = os.getenv("SESSION_ID", "voice")

# ---- Porcupine wake word ----
import pvporcupine
from pvrecorder import PvRecorder

WAKE_WORD = os.getenv("WAKE_WORD", "porcupine")  # try 'computer' if you have that keyword

# ---- OpenAI client ----
from openai import OpenAI
oai = OpenAI(api_key=OPENAI_API_KEY)

SAMPLE_RATE = 16000
CHANNELS = 1

def record_seconds(seconds=6):
    print(f"[rec] recording {seconds}s…")
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                    channels=CHANNELS, dtype='int16')
    sd.wait()
    return frames

def wav_bytes_from_int16(int16_np):
    bio = io.BytesIO()
    sf.write(bio, int16_np.astype(np.int16), SAMPLE_RATE, format='WAV')
    bio.seek(0)
    return bio

def transcribe(frames):
    wavfile = wav_bytes_from_int16(frames)
    tr = oai.audio.transcriptions.create(
        model="whisper-1",
        file=("speech.wav", wavfile, "audio/wav")
    )
    return tr.text.strip()

def ask_backend(text):
    r = requests.post(f"{BACKEND_BASE}/api/ask",
                      json={"q": text, "session_id": SESSION_ID}, timeout=60)
    r.raise_for_status()
    return r.json()["answer"]

def tts_wav_bytes(text):
    # gpt-4o-mini-tts can return wav; falls back to standard if not available in your account
    speech = oai.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text,
        format="wav"
    )
    # SDK returns bytes-like
    data = speech.read()
    return io.BytesIO(data)

def play_wav(bio):
    bio.seek(0)
    data, sr = sf.read(bio, dtype='float32')
    sd.play(data, sr)
    sd.wait()

def main():
    print("[voice] loading Porcupine…")
    porcupine = pvporcupine.create(access_key=os.getenv("PICOVOICE_ACCESS_KEY"),
                                   keywords=[WAKE_WORD])
    rec = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    print(f"[voice] device: {rec.selected_device}, wake word: {WAKE_WORD}")
    rec.start()
    try:
      while True:
        frame = rec.read()
        result = porcupine.process(frame)
        if result >= 0:
            print("[voice] Wake word detected! Speak after the beep…")
            # short beep (play 300 Hz tone)
            t = np.linspace(0, 0.2, int(SAMPLE_RATE*0.2), False)
            beep = 0.2*np.sin(2*np.pi*300*t).astype(np.float32)
            sd.play(beep, SAMPLE_RATE); sd.wait()

            audio = record_seconds(6)
            try:
                text = transcribe(audio)
                if not text:
                    print("[voice] (empty transcription)")
                    continue
                print(f"[you] {text}")

                answer = ask_backend(text)
                print(f"[ai] {answer}")

                wav = tts_wav_bytes(answer)
                play_wav(wav)
            except Exception as e:
                print("error:", e)
    finally:
      rec.stop(); rec.delete(); porcupine.delete()

if __name__ == "__main__":
    main()
