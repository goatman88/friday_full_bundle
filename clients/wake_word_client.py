import os, sys, time, base64, io, wave, struct
import httpx
from pydub import AudioSegment

# --- CONFIG ---
BACKEND = os.getenv("BACKEND", "https://friday-099e.onrender.com")
HOTWORD = os.getenv("HOTWORD", "porcupine")  # the built-in demo hotword
PV_KEY  = os.getenv("PICOVOICE_ACCESS_KEY")  # set your Picovoice key

# --- deps: pip install pvporcupine sounddevice pydub httpx ---
import pvporcupine
import sounddevice as sd

def record_seconds(seconds=4, samplerate=16000, channels=1):
    print(f"Recording {seconds}s…")
    audio = sd.rec(int(seconds*samplerate), samplerate=samplerate, channels=channels, dtype='int16')
    sd.wait()
    return audio, samplerate

def wav_bytes_from_pcm(pcm, samplerate):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()

def play_wav_b64(b64):
    audio = AudioSegment.from_file(io.BytesIO(base64.b64decode(b64)))
    audio.export("reply.wav", format="wav")
    try:
        import simpleaudio as sa  # pip install simpleaudio
        sa.WaveObject.from_wave_file("reply.wav").play()
    except Exception:
        pass

async def call_backend_text(q: str):
    async with httpx.AsyncClient(timeout=120) as client:
        a = await client.post(f"{BACKEND}/api/ask", json={"q": q})
        a.raise_for_status()
        answer = a.json()["answer"]
        t = await client.post(f"{BACKEND}/api/tts", json={"text": answer})
        t.raise_for_status()
        b64 = t.json()["audio_wav_b64"]
        play_wav_b64(b64)

def main():
    if not PV_KEY:
        print("Set PICOVOICE_ACCESS_KEY")
        sys.exit(1)

    porcupine = pvporcupine.create(access_key=PV_KEY, keywords=[HOTWORD])
    samplerate = porcupine.sample_rate
    frame_length = porcupine.frame_length

    with sd.InputStream(channels=1, samplerate=samplerate, dtype='int16') as stream:
        print("Listening for wake word…")
        while True:
            frame, _ = stream.read(frame_length)
            pcm = frame.flatten()
            result = porcupine.process(pcm)
            if result >= 0:
                print("Wake word detected!")
                audio, sr = record_seconds(4, samplerate=samplerate, channels=1)
                wav_bytes = wav_bytes_from_pcm(audio, sr)

                # STT
                with httpx.Client(timeout=120) as client:
                    files = {'audio': ('speech.wav', wav_bytes, 'audio/wav')}
                    stt_res = client.post(f"{BACKEND}/api/stt", files=files)
                    stt_res.raise_for_status()
                    text = stt_res.json().get("text", "")
                print("Heard:", text)
                import anyio
                anyio.run(call_backend_text, text)

if __name__ == "__main__":
    main()

