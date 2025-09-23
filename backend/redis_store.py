# backend/redis_store.py
import os
import json
from typing import Optional, Dict, Any
from redis.asyncio import Redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_redis: Optional[Redis] = None

async def get_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis

async def create_session(sid: str):
    r = await get_client()
    await r.hset(f"sess:{sid}", mapping={"messages": json.dumps([])})

async def append_message(sid: str, role: str, content: str):
    r = await get_client()
    raw = await r.hget(f"sess:{sid}", "messages")
    msgs = json.loads(raw or "[]")
    msgs.append({"role": role, "content": content})
    await r.hset(f"sess:{sid}", mapping={"messages": json.dumps(msgs)})

async def get_messages(sid: str) -> list[Dict[str, Any]]:
    r = await get_client()
    raw = await r.hget(f"sess:{sid}", "messages")
    return json.loads(raw or "[]")

# --- Wake flag (simple queue) ---
async def push_wake():
    r = await get_client()
    # push to a list; frontend pops
    await r.lpush("wake:queue", "wake")

async def pop_wake(timeout_sec: int = 25) -> Optional[str]:
    r = await get_client()
    item = await r.brpop("wake:queue", timeout=timeout_sec)
    if not item:
        return None
    # item is tuple (key, value)
    return item[1]
