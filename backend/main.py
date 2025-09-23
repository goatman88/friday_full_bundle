# backend/main.py
# FastAPI backend: health checks, /api/ask (OpenAI), and a secure
# WebRTC SDP proxy for OpenAI Realtime.

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import os
import httpx
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    # We don't crash the app, but we will 500 on calls that need it.
    pass

# You can change this to the Realtime model you want to target
REALTIME_MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")

app = FastAPI(title="Friday Backend")

# CORS for your Vite dev server and Render preview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Health ----------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------- /api/ask (Chat) ----------
# Expects JSON: { "q": "your question" }
# Returns: { "answer": "..." }
@app.post("/api/ask")
async def api_ask(req: Request):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    body = await req.json()
    user_msg = (body.get("q") or "").strip()
    if not user_msg:
        return {"answer": ""}

    client = OpenAI(api_key=OPENAI_API_KEY)
    # Use a fast, low-cost model — adjust as you like
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": user_msg}],
    )
    answer = resp.choices[0].message.content
    return {"answer": answer}

# ---------- /api/session (optional helper) ----------
# Creates a short-lived Realtime session metadata.
# The browser can use this JSON for client-side flows that need it.
@app.post("/api/session")
async def api_session():
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {"model": REALTIME_MODEL, "voice": "verse"}  # voice is optional

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        try:
            data = r.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Invalid response from OpenAI")
    return JSONResponse(content=data, status_code=r.status_code)

# ---------- /api/realtime/sdp (SDP Proxy) ----------
# Secure server-side SDP exchange so your API key never touches the browser.
#
# Browser POSTs the local offer SDP (plain text). We forward it to OpenAI’s
# Realtime REST endpoint and return the answer SDP (also plain text).
#
# Frontend usage:
#   const answer = await fetch("/api/realtime/sdp", { method: "POST", body: offer.sdp }).then(r => r.text());
#   await pc.setRemoteDescription({ type: "answer", sdp: answer });
@app.post("/api/realtime/sdp")
async def api_realtime_sdp(request: Request):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    offer_sdp = await request.body()
    if not offer_sdp:
        raise HTTPException(status_code=400, detail="Missing SDP offer")

    url = f"https://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",
        # Some deployments still expect this header (kept for compatibility)
        "OpenAI-Beta": "realtime=v1",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, content=offer_sdp)
        # The Realtime REST returns the SDP answer as text/plain
        answer_sdp = r.text
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=answer_sdp)
        return PlainTextResponse(answer_sdp, status_code=200)
