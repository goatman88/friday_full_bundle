# Minimal “wake server” so the client can connect and you can
# later drop Porcupine in. We keep it running even if Porcupine
# wheels aren’t available on Windows.

import asyncio, json
import websockets

HOST, PORT = "localhost", 8765

async def handler(ws, path):
    await ws.send(json.dumps({"ready": True, "wake_supported": False}))
    # you can forward keyboard-triggered events from the client if you want
    async for msg in ws:
        await ws.send(json.dumps({"ack": msg}))

async def main():
    print(f"Wake/ws on ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())


