import os, sounddevice as sd, numpy as np, pvporcupine, queue, requests

ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")  # set in shell
WAKEWORD = "hey google"  # choose from built-ins (or your custom keyword)

# When triggered, record ~4 seconds and send to STT endpoint
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

def record_seconds(sec=4, samplerate=16000):
    frames = int(sec * samplerate)
    data = sd.rec(frames, samplerate=samplerate, channels=1, dtype="int16")
    sd.wait()
    return data.tobytes()

def main():
    porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=[WAKEWORD])
    q = queue.Queue()

    def callback(indata, frames, t, status):
        if status: print(status)
        q.put(bytes(indata))

    stream = sd.RawInputStream(samplerate=porcupine.sample_rate, blocksize=porcupine.frame_length,
                               channels=1, dtype='int16', callback=callback)
    print("Listening for wake word:", WAKEWORD)
    with stream:
        while True:
            pcm = q.get()
            pcm_np = np.frombuffer(pcm, dtype=np.int16)
            result = porcupine.process(pcm_np)
            if result >= 0:
                print("Wake word detected! Recording…")
                audio = record_seconds(4, porcupine.sample_rate)
                files = {"file": ("speech.wav", audio, "audio/wav")}
                r = requests.post(f"{BACKEND}/api/stt", files=files, timeout=60)
                print("You said:", r.json().get("text"))

if __name__ == "__main__":
    main()
