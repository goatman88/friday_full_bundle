import os
import json
import uuid
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, Request, Response, HTTPException, Path, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .redis_store import (
    create_session, append_message, get_messages,
    rt_append, rt_get_all, rt_clear, session_reset,
    push_wake, pop_wake, get_client
)

APP_STARTED = time.time()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TEXT_MODEL      = os.environ.get("TEXT_MODEL", "gpt-4o")
REALTIME_MODEL  = os.environ.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE  = os.environ.get("REALTIME_VOICE", "verse")
CORS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set")

app = FastAPI(title="Friday API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if CORS == ["*"] else CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _now_ts() -> float:
    return datetime.now(tz=timezone.utc).timestamp()

# ---------------- Health ----------------
@app.get("/health")
def health_root():
    return {"status": "ok"}

@app.get("/api/health")
def health_api():
    return {"status": "ok"}

# ---------------- Sessions ----------------
@app.get("/session")
async def get_session():
    sid = str(uuid.uuid4())
    await create_session(sid)
    return {
        "session_id": sid,
        "realtime": {"model": REALTIME_MODEL, "voice": REALTIME_VOICE},
        "text_model": TEXT_MODEL,
    }

@app.post("/session/{sid}/reset")
async def post_reset_session(sid: str = Path(...)):
    await session_reset(sid)
    return {"ok": True}

# ---------------- /api/ask ----------------
@app.post("/api/ask")
async def ask(request: Request):
    body = await request.json()
    q = (body.get("q") or "").strip()
    if not q:
        raise HTTPException(400, "Missing 'q'")

    session_id: Optional[str] = body.get("session_id")
    latency = (body.get("latency") or "").strip().lower()

    text_model = TEXT_MODEL
    if latency == "balanced":
        text_model = "gpt-4o-mini"
    elif latency == "ultra":
        text_model = "gpt-4o-mini"

    msgs = [
        {"role": "system", "content": "You are a concise, helpful assistant."},
        {"role": "user", "content": q},
    ]

    if session_id:
        await rt_append(session_id, {"kind": "note", "text": f"USER: {q}", "ts": _now_ts()})
        await append_message(session_id, "user", q)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {"model": text_model, "messages": msgs, "temperature": 0.3}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        answer = data["choices"][0]["message"]["content"]

        if session_id:
            await append_message(session_id, "assistant", answer)
            await rt_append(session_id, {"kind": "final", "text": f"ASSISTANT: {answer}", "ts": _now_ts()})

        return {"answer": answer}

# ---------------- Realtime SDP proxy ----------------
@app.post("/realtime/sdp", response_class=PlainTextResponse)
async def sdp_proxy(request: Request):
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    q = dict(request.query_params)
    latency = q.get("latency", "").lower()

    model = REALTIME_MODEL
    if latency == "balanced":
        model = "gpt-4o-realtime-preview"
    elif latency == "ultra":
        model = "gpt-4o-realtime-preview-lite"

    sdp_text = body.decode("utf-8")
    if "application/json" in content_type:
        try:
            sdp_text = json.loads(sdp_text)["sdp"]
        except Exception:
            raise HTTPException(400, "Invalid JSON offer")

    openai_url = f"https://api.openai.com/v1/realtime?model={model}&voice={REALTIME_VOICE}"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/sdp"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(openai_url, headers=headers, content=sdp_text)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        return Response(content=r.text, media_type="application/sdp")

# ---------------- Ephemeral token (Direct Realtime) ----------------
@app.post("/ephemeral")
async def ephemeral_token_post(request: Request):
    body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    return await _issue_ephemeral(model_hint=(body.get("latency") or ""))

@app.get("/ephemeral")
async def ephemeral_token_get(latency: Optional[str] = None):
    return await _issue_ephemeral(model_hint=(latency or ""))

async def _issue_ephemeral(model_hint: str = ""):
    latency = (model_hint or "").lower()
    model = REALTIME_MODEL
    if latency == "balanced":
        model = "gpt-4o-realtime-preview"
    elif latency == "ultra":
        model = "gpt-4o-realtime-preview-lite"

    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "voice": REALTIME_VOICE, "ttl": 60}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        try:
            token = data["client_secret"]["value"]
        except Exception:
            raise HTTPException(500, "Unexpected token response")
        return {"ephemeral_token": token}

# ---------------- Wake trigger endpoints ----------------
@app.post("/wake")
async def wake_post():
    await push_wake()
    return {"ok": True}

@app.get("/wake/next")
async def wake_next():
    item = await pop_wake(timeout_sec=25)
    return {"wake": bool(item)}

# ---------------- Realtime transcript log API ----------------
@app.post("/session/{sid}/log/append")
async def append_rt_log(request: Request, sid: str = Path(...)):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Missing 'text'")
    kind = (body.get("kind") or "partial").lower()
    if kind not in ("partial", "final", "note"):
        kind = "partial"
    payload = {"text": text, "kind": kind, "ts": body.get("ts", _now_ts())}
    await rt_append(sid, payload)
    return {"ok": True}

@app.get("/session/{sid}/log")
async def get_rt_log(sid: str = Path(...), download: Optional[int] = None):
    data = await rt_get_all(sid)
    if download:
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{sid}-rtlog.json"'}
        )
    return {"items": data}

@app.get("/session/{sid}/log.txt", response_class=PlainTextResponse)
async def get_rt_log_txt(sid: str = Path(...)):
    items = await rt_get_all(sid)
    lines = []
    for it in items:
        ts = it.get("ts") or _now_ts()
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        lines.append(f"[{dt}] {it.get('kind','note').upper()}: {it.get('text','')}")
    return "\n".join(lines) + ("\n" if lines else "")

# NEW: delete/clear transcript
@app.delete("/session/{sid}/log")
async def delete_rt_log(sid: str = Path(...)):
    await rt_clear(sid)
    return {"ok": True}

# NEW: Live SSE stream of transcript with event typing and filtering
@app.get("/session/{sid}/log/stream")
async def sse_stream(
    sid: str = Path(...),
    kinds: Optional[str] = Query(None, description="csv of kinds: partial,final,note")
):
    """
    SSE with event names matching payload.kind (partial|final|note).
    Use ?kinds=final to only receive final lines, or omit for all.
    """
    filter_set = None
    if kinds:
        filter_set = {k.strip().lower() for k in kinds.split(",") if k.strip()}

    async def event_generator():
        r = await get_client()
        key = f"sess:{sid}:rtlog"
        idx = await r.llen(key) or 0

        # send existing first
        if idx:
            chunk = await r.lrange(key, 0, idx - 1)
            for raw in chunk:
                try:
                    j = json.loads(raw)
                except Exception:
                    j = {"kind": "note", "text": raw}
                if (filter_set is None) or (j.get("kind") in filter_set):
                    yield f"event: {j.get('kind','note')}\n"
                    yield f"data: {json.dumps(j, ensure_ascii=False)}\n\n"

        # tail loop
        while True:
            now_len = await r.llen(key)
            if now_len > idx:
                chunk = await r.lrange(key, idx, now_len - 1)
                idx = now_len
                for raw in chunk:
                    try:
                        j = json.loads(raw)
                    except Exception:
                        j = {"kind": "note", "text": raw}
                    if (filter_set is None) or (j.get("kind") in filter_set):
                        yield f"event: {j.get('kind','note')}\n"
                        yield f"data: {json.dumps(j, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# NEW: metrics snapshot + SSE metrics stream
@app.get("/metrics")
async def metrics_once():
    r = await get_client()
    try:
        pong = await r.ping()
    except Exception:
        pong = False
    return {
        "uptime_sec": int(time.time() - APP_STARTED),
        "redis_ok": bool(pong),
        "text_model": TEXT_MODEL,
        "realtime_model": REALTIME_MODEL,
        "voice": REALTIME_VOICE,
    }

@app.get("/metrics/stream")
async def metrics_stream():
    async def gen():
        r = await get_client()
        while True:
            try:
                pong = await r.ping()
            except Exception:
                pong = False
            snap = {
                "ts": _now_ts(),
                "uptime_sec": int(time.time() - APP_STARTED),
                "redis_ok": bool(pong),
            }
            yield f"data: {json.dumps(snap)}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")





