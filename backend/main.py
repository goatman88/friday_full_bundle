import os
import json
import asyncio
import logging
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── OpenAI SDK (Responses API) ──────────────────────────────
from openai import OpenAI
import httpx
import websockets

# ────────────────────────────────────────────────────────────
# ENV / Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    print("WARN: OPENAI_API_KEY is not set. /api/ask, /session, /realtime will fail.")

client = OpenAI(api_key=OPENAI_API_KEY)

# ────────────────────────────────────────────────────────────
# FastAPI app
app = FastAPI(title="Friday Backend")

# CORS (dev-friendly; tighten for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────────────────────
# Health

@app.get("/health")
def root_health():
    return {"status": "ok"}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}

# ────────────────────────────────────────────────────────────
# Ask (Responses API)

class AskBody(BaseModel):
    question: str

@app.post("/api/ask")
async def api_ask(body: AskBody):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY missing"}, status_code=500)
    try:
        # Minimal Responses call
        resp = client.responses.create(
            model=TEXT_MODEL,
            input=f"Answer concisely: {body.question}"
        )
        # Pull the text safely
        answer = ""
        if resp.output and len(resp.output) > 0:
            # The first output item typically contains the text
            first = resp.output[0]
            if getattr(first, "content", None) and len(first.content) > 0:
                answer = first.content[0].text
        if not answer:
            answer = "No answer returned."
        return {"answer": answer}
    except Exception as e:
        logging.exception("ask failed")
        return JSONResponse({"error": str(e)}, status_code=500)

# ────────────────────────────────────────────────────────────
# Ephemeral key for Direct WebRTC (browser will call this)

SESSION_URL = "https://api.openai.com/v1/realtime/sessions"

@app.get("/session")
async def get_ephemeral_session():
    """
    Mint a short-lived client_secret for WebRTC browser usage.
    Returns shape: { "client_secret": { "value": "..." }, ... }
    """
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY missing"}, status_code=500)

    payload = {
        "model": REALTIME_MODEL,
        # Optional voice; browser can ignore if you're text-only:
        "voice": os.getenv("REALTIME_VOICE", "verse"),
        # TTL is controlled by OpenAI; you can add metadata if you want
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1"
    }

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(SESSION_URL, headers=headers, json=payload)
        if r.status_code != 200:
            return JSONResponse({"error": r.text}, status_code=r.status_code)
        return JSONResponse(r.json())

# ────────────────────────────────────────────────────────────
# WebSocket proxy to OpenAI Realtime (server-bridge)

async def pipe_ws(client_ws: WebSocket, oai_ws):
    """
    Bi-directional piping: browser WS <-> OpenAI WS
    - For text frames: we pass raw strings.
    - For binary frames (if any): we pass bytes.
    """
    async def from_client():
        try:
            while True:
                msg = await client_ws.receive()
                if "text" in msg and msg["text"] is not None:
                    await oai_ws.send(msg["text"])
                elif "bytes" in msg and msg["bytes"] is not None:
                    await oai_ws.send(msg["bytes"])
        except Exception:
            pass  # handled by caller

    async def from_openai():
        try:
            async for message in oai_ws:
                # message can be str or bytes
                if isinstance(message, (bytes, bytearray)):
                    await client_ws.send_bytes(message)
                else:
                    await client_ws.send_text(message)
        except Exception:
            pass  # handled by caller

    await asyncio.gather(from_client(), from_openai())

@app.websocket("/realtime")
async def realtime_proxy(ws: WebSocket):
    """
    Browser connects here: ws://localhost:8000/realtime
    We connect server-side to OpenAI Realtime over secure WS and relay messages.
    """
    await ws.accept()
    if not OPENAI_API_KEY:
        await ws.send_text(json.dumps({"error": "OPENAI_API_KEY missing"}))
        await ws.close()
        return

    # Build OpenAI Realtime WS URL
    oai_url = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = [
        ("Authorization", f"Bearer {OPENAI_API_KEY}"),
        ("OpenAI-Beta", "realtime=v1"),
    ]

    try:
        async with websockets.connect(oai_url, extra_headers=headers, max_size=None) as oai_ws:
            await pipe_ws(ws, oai_ws)
    except WebSocketDisconnect:
        # client closed
        pass
    except Exception as e:
        logging.exception("realtime proxy error")
        try:
            await ws.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
        finally:
            try:
                await ws.close()
            except Exception:
                pass

