import os, queue, sounddevice as sd, numpy as np
from dotenv import load_dotenv
load_dotenv()
ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")

import pvporcupine

porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=["jarvis","computer"])
q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(indata.copy())

with sd.InputStream(channels=1, samplerate=16000, dtype='int16', callback=callback):
    print("Listening for wake words: jarvis / computer")
    while True:
        pcm = q.get()
        pcm = np.frombuffer(pcm, dtype=np.int16)
        result = porcupine.process(pcm)
        if result >= 0:
            print("Wake word detected!")
            # TODO: trigger WebSocket session / TTS, etc.
