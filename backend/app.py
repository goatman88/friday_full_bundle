@'
import os, base64, json
from typing import Optional, Dict
from fastapi import FastAPI, APIRouter, HTTPException, Body, Header
from pydantic import BaseModel
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-4o-mini")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "verse")

app = FastAPI(title="Friday Backend", version="1.0.0")
api = APIRouter(prefix="/api")

class AskIn(BaseModel):
    q: str

class AskOut(BaseModel):
    answer: str

class SessionIn(BaseModel):
    device: Optional[str] = None
    user: Optional[str] = None

class SessionOut(BaseModel):
    session_id: str
    text_model: str
    realtime_model: str
    realtime_voice: str

class SDPIn(BaseModel):
    sdp: str
    model: Optional[str] = None
    voice: Optional[str] = None

class SDPOut(BaseModel):
    answer: str

@app.get("/health")
def root_health() -> Dict[str, str]:
    return {"status":"ok"}

@api.get("/health")
def api_health() -> Dict[str, str]:
    return {"status":"ok"}

@api.post("/ask", response_model=AskOut)
async def ask(body: AskIn) -> AskOut:
    q = body.q.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    if not OPENAI_API_KEY:
        return AskOut(answer=f"You asked: {q}")
    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": TEXT_MODEL, "input": f"Answer briefly:\n\n{q}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        try:
            ans = data["output"][0]["content"][0]["text"]
        except Exception:
            ans = json.dumps(data)[:500]
    return AskOut(answer=ans)

@api.post("/session", response_model=SessionOut)
async def session(_body: SessionIn) -> SessionOut:
    sid = base64.urlsafe_b64encode(os.urandom(9)).decode().rstrip("=")
    return SessionOut(
        session_id=f"local-{sid}",
        text_model=TEXT_MODEL,
        realtime_model=REALTIME_MODEL,
        realtime_voice=REALTIME_VOICE,
    )

@api.post("/sdp", response_model=SDPOut)
async def sdp_proxy(body: SDPIn) -> SDPOut:
    if not OPENAI_API_KEY:
        return SDPOut(answer="Server missing OPENAI_API_KEY; cannot open realtime session.")
    model = body.model or REALTIME_MODEL
    voice = body.voice or REALTIME_VOICE
    url = "https://api.openai.com/v1/realtime/sdp"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",
        "X-Requested-Model": model,
        "X-Requested-Voice": voice,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(url, headers=headers, content=body.sdp.encode("utf-8"))
        r.raise_for_status()
        answer_sdp = r.text
    return SDPOut(answer=answer_sdp)

app.include_router(api)
'@ | Set-Content -Encoding UTF8 .\app.py












