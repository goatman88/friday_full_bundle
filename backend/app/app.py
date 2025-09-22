from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import asyncio, json, os, base64, httpx, redis.asyncio as redis

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
TTS_VOICE   = os.getenv("OPENAI_TTS_VOICE", "alloy")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")

rds = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

app = FastAPI()
origins = ["http://localhost:5173", "https://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.get("/health") 
def health_root(): return {"status": "ok"}
@app.get("/api/health")
def health_api():   return {"status": "ok"}

# ---------- models ----------
class AskIn(BaseModel):
    session_id: str
    q: str

# ---------- helpers ----------
async def save_turn(session_id: str, role: str, content: str):
    key = f"hist:{session_id}"
    await rds.rpush(key, json.dumps({"role": role, "content": content}))

async def get_history(session_id: str, last: int|None=None):
    key = f"hist:{session_id}"
    items = await rds.lrange(key, -last if last else 0, -1) if last else await rds.lrange(key, 0, -1)
    return [json.loads(x) for x in items]

# ---------- SSE streaming chat ----------
@app.post("/api/ask/stream")
async def ask_stream(body: AskIn):
    if not OPENAI_KEY: raise HTTPException(500, "OPENAI_API_KEY missing")
    await save_turn(body.session_id, "user", body.q)

    async def gen():
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        hist = await get_history(body.session_id, last=20)
        messages = [{"role": x["role"], "content": x["content"]} for x in hist] + [{"role":"user","content":body.q}]
        payload = {"model": CHAT_MODEL, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"): continue
                    data = line[5:].strip()
                    if data == "[DONE]": break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                        if delta:
                            yield f"data: {json.dumps({'delta': delta})}\n\n"
                    except Exception:
                        continue
        # small marker end
        yield "data: {\"done\":true}\n\n"

    return EventSourceResponse(gen(), media_type="text/event-stream")

# ---------- WebSocket proxy to OpenAI Realtime ----------
@app.websocket("/ws/realtime")
async def ws_realtime(ws: WebSocket):
    await ws.accept()
    if not OPENAI_KEY:
        await ws.close(1011); return
    # connect to OpenAI realtime websocket
    rt_url = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = [("Authorization", f"Bearer {OPENAI_KEY}")]
    import websockets
    try:
        async with websockets.connect(rt_url, extra_headers=headers, ping_interval=20, open_timeout=15) as oai:
            async def to_openai():
                try:
                    async for msg in ws.iter_text():
                        await oai.send(msg)
                except WebSocketDisconnect:
                    await oai.close()
            async def to_browser():
                async for msg in oai:
                    await ws.send_text(msg)
            await asyncio.gather(to_openai(), to_browser())
    except Exception as e:
        await ws.send_text(json.dumps({"type":"error","message":str(e)}))
        await ws.close()

# ---------- Vision upload ----------
@app.post("/api/vision")
async def vision(file: UploadFile = File(...)):
    if not OPENAI_KEY: raise HTTPException(500, "OPENAI_API_KEY missing")
    img = await file.read()
    b64 = base64.b64encode(img).decode("utf-8")
    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role":"user",
            "content":[
                {"type":"text","text":"Describe this image briefly."},
                {"type":"input_image","image_data": b64}
            ]
        }]
    }
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
            json=payload)
    data = res.json()
    text = data["choices"][0]["message"]["content"]
    return {"answer": text}

# ---------- STT (upload audio/wav) ----------
@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    if not OPENAI_KEY: raise HTTPException(500, "OPENAI_API_KEY missing")
    async with httpx.AsyncClient(timeout=120) as client:
        form = httpx.MultipartWriter()
        form.add_part(b"whisper-1", name="model")
        form.add_part(await file.read(), name="file", filename=file.filename, content_type=file.content_type)
        res = await client.post("https://api.openai.com/v1/audio/transcriptions",
                                headers={"Authorization": f"Bearer {OPENAI_KEY}"}, content=form)
    return res.json()

# ---------- TTS ----------
class TtsIn(BaseModel):
    text: str
@app.post("/api/tts")
async def tts(body: TtsIn):
    if not OPENAI_KEY: raise HTTPException(500, "OPENAI_API_KEY missing")
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post("https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
            json={"model":"gpt-4o-mini-tts","voice":TTS_VOICE,"input":body.text})
    if res.status_code != 200:
        raise HTTPException(500, res.text)
    return StreamingResponse(iter([res.content]), media_type="audio/mpeg")

# ---------- History ----------
@app.get("/api/history/{session_id}")
async def get_hist(session_id: str):
    return await get_history(session_id)









