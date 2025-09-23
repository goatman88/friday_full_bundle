import os
import json
from typing import Optional, Dict, Any, List
from redis.asyncio import Redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_redis: Optional[Redis] = None

async def get_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis

# ------------ Chat messages (for /api/ask) ------------
async def create_session(sid: str):
    r = await get_client()
    pipe = r.pipeline()
    pipe.hset(f"sess:{sid}", mapping={"messages": json.dumps([])})
    pipe.delete(f"sess:{sid}:rtlog")  # realtime transcript list
    await pipe.execute()

async def append_message(sid: str, role: str, content: str):
    r = await get_client()
    raw = await r.hget(f"sess:{sid}", "messages")
    msgs = json.loads(raw or "[]")
    msgs.append({"role": role, "content": content})
    await r.hset(f"sess:{sid}", mapping={"messages": json.dumps(msgs)})

async def get_messages(sid: str) -> List[Dict[str, Any]]:
    r = await get_client()
    raw = await r.hget(f"sess:{sid}", "messages")
    return json.loads(raw or "[]")

# ------------ Realtime transcript log ------------
async def rt_append(sid: str, payload: Dict[str, Any]):
    """
    payload := { kind: "partial"|"final"|"note", text: str, ts?: number }
    Stored as JSONL entries in a Redis list.
    """
    r = await get_client()
    await r.rpush(f"sess:{sid}:rtlog", json.dumps(payload, ensure_ascii=False))

async def rt_get_all(sid: str) -> List[Dict[str, Any]]:
    r = await get_client()
    arr = await r.lrange(f"sess:{sid}:rtlog", 0, -1)
    return [json.loads(x) for x in (arr or [])]

async def session_reset(sid: str):
    r = await get_client()
    pipe = r.pipeline()
    pipe.hset(f"sess:{sid}", mapping={"messages": json.dumps([])})
    pipe.delete(f"sess:{sid}:rtlog")
    await pipe.execute()

# ------------ Wake flag (simple queue) ------------
async def push_wake():
    r = await get_client()
    await r.lpush("wake:queue", "wake")

async def pop_wake(timeout_sec: int = 25):
    r = await get_client()
    item = await r.brpop("wake:queue", timeout=timeout_sec)
    if not item:
        return None
    return item[1]

