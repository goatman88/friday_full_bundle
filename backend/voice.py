import os, sys, time
from dotenv import load_dotenv; load_dotenv()
ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
if not ACCESS_KEY: print("PICOVOICE_ACCESS_KEY missing"); sys.exit(1)

from pvporcupine import create
import sounddevice as sd
import numpy as np

handle = create(access_key=ACCESS_KEY, keywords=['picovoice'])
rate = handle.sample_rate
frame_len = handle.frame_length
print("Wake word engine ready. Say: 'picovoice'")

def cb(indata, frames, time_, status):
    pcm = (indata[:,0] * 32767).astype(np.int16)
    if handle.process(pcm) >= 0:
        print("🔥 Wake word detected!")
        # TODO: call your local endpoint or bring window to foreground

with sd.InputStream(channels=1, samplerate=rate, blocksize=frame_len, callback=cb):
    while True: time.sleep(0.1)
