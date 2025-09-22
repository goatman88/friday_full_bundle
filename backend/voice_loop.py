import os, asyncio, json
from websockets.server import serve
from dotenv import load_dotenv

load_dotenv()
PICO_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")
WAKE_WORD = os.getenv("WAKE_WORD", "porcupine")  # built-in keyword name

# If pvporcupine/pvrecorder are installed, import them; otherwise degrade to hotkey
try:
    import pvporcupine
    from pvrecorder import PvRecorder
    HAVE_PV = True
except Exception:
    HAVE_PV = False

CLIENTS = set()

async def broadcast(msg):
    dead = set()
    for ws in CLIENTS:
        try:
            await ws.send(msg)
        except:
            dead.add(ws)
    CLIENTS.difference_update(dead)

async def ws_server():
    async def handler(ws):
        CLIENTS.add(ws)
        try:
            async for _ in ws:
                pass
        finally:
            CLIENTS.discard(ws)
    async with serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()

async def loop_hotkey():  # fallback: press ENTER in this console to "wake"
    print("[voice] Hotkey mode. Press ENTER to trigger wake.")
    loop = asyncio.get_running_loop()
    while True:
        await loop.run_in_executor(None, input)
        await broadcast(json.dumps({"event":"wake"}))

async def loop_porcupine():
    print("[voice] Porcupine mode.")
    porcupine = pvporcupine.create(access_key=PICO_KEY, keyword_paths=None, keywords=[WAKE_WORD])
    recorder = PvRecorder(frame_length=porcupine.frame_length, device_index=-1)
    recorder.start()
    try:
        while True:
            frame = recorder.read()
            res = porcupine.process(frame)
            if res >= 0:
                await broadcast(json.dumps({"event":"wake"}))
    finally:
        recorder.stop(); recorder.delete(); porcupine.delete()

async def main():
    listeners = [ws_server()]
    listeners.append(loop_porcupine() if HAVE_PV and PICO_KEY else loop_hotkey())
    await asyncio.gather(*listeners)

if __name__ == "__main__":
    asyncio.run(main())

