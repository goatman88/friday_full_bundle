import os, json
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import aioredis

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_HISTORY = int(os.getenv("HISTORY_MAX", "20"))

_redis = None
async def get_redis():
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis

class AskBody(BaseModel):
    q: str
    session: Optional[str] = "default"

def build_prompt(history: List[Dict], q: str) -> List[Dict]:
    msgs: List[Dict] = [{"role":"system","content":"You are Friday, a concise helpful assistant."}]
    for item in history[-MAX_HISTORY:]:
        msgs.append({"role": item.get("role","user"), "content": item.get("text","")})
    msgs.append({"role":"user","content":q})
    return msgs

@router.post("/api/ask")
async def ask(body: AskBody):
    q = (body.q or "").strip()
    if not q:
        raise HTTPException(400, "q required")
    # history
    r = await get_redis()
    key = f"hist:{body.session}"
    prev = await r.lrange(key, 0, -1)
    hist = [json.loads(x) for x in prev] if prev else []
    msgs = build_prompt(hist, q)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=msgs,
            temperature=0.6,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        raise HTTPException(500, f"OpenAI error: {e}")

    # persist
    await r.rpush(key, json.dumps({"role":"user","text":q}))
    await r.rpush(key, json.dumps({"role":"assistant","text":answer}))
    await r.ltrim(key, -200, -1)  # keep last 200 items

    return {"text": answer}
