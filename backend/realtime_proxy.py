import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
import httpx

router = APIRouter()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")

@router.post("/api/realtime/sdp", response_class=PlainTextResponse)
async def realtime_sdp(request: Request, x_model: str = Header(default=None)):
    """
    Browser sends offer SDP (Content-Type: application/sdp) here.
    We forward it to OpenAI, return the answer SDP. API key stays server-side.
    Optional header `x-model` to override model per-call.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY not configured")
    offer_sdp = await request.body()
    model = (x_model or REALTIME_MODEL)

    url = f"https://api.openai.com/v1/realtime?model={model}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/sdp",
    }
    try:
        async with httpx.AsyncClient(timeout=60) as cli:
            resp = await cli.post(url, headers=headers, content=offer_sdp)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text)
        return resp.text
    except httpx.HTTPError as e:
        raise HTTPException(500, f"Realtime proxy error: {e}")
