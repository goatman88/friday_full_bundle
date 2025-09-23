import os, json, asyncio
from fastapi import APIRouter, HTTPException
import aioredis

router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_pool = None

async def get_redis():
    global _pool
    if _pool is None:
        _pool = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _pool

@router.get("/api/history/{session_id}")
async def get_history(session_id: str):
    r = await get_redis()
    vals = await r.lrange(f"hist:{session_id}", 0, -1)
    return [json.loads(v) for v in vals]

@router.post("/api/history/{session_id}")
async def append_history(session_id: str, item: dict):
    r = await get_redis()
    await r.rpush(f"hist:{session_id}", json.dumps(item))
    await r.ltrim(f"hist:{session_id}", -200, -1)  # keep last 200
    return {"ok": True}

