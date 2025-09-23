"""
tools/wake_word.py

Local wake-word helper using Picovoice Porcupine.
When wake is detected, POSTs to http://localhost:8000/wake (adjust for Render).

Requirements:
  pip install pvporcupine pvrecorder requests

Environment:
  set PICOVOICE_ACCESS_KEY=...  (https://console.picovoice.ai/)
"""
import os
import time
import requests
import pvporcupine
from pvrecorder import PvRecorder

ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY")
BACKEND = os.environ.get("BACKEND_BASE", "http://localhost:8000")
WAKE_ENDPOINT = f"{BACKEND}/wake"

def main():
    if not ACCESS_KEY:
        print("PICOVOICE_ACCESS_KEY env var is required")
        return

    porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=["jarvis", "computer", "alexa", "picovoice"])  # pick one you like
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    try:
        recorder.start()
        print("Listening for wake word… (Ctrl+C to stop)")
        while True:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            if result >= 0:
                print("Wake detected, notifying backend…")
                try:
                    requests.post(WAKE_ENDPOINT, timeout=3)
                except Exception as e:
                    print("wake POST failed:", e)
                time.sleep(1.0)  # simple debounce
    except KeyboardInterrupt:
        pass
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()

if __name__ == "__main__":
    main()
