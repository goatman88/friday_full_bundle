
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

async def token_generator(prompt: str):
    # demo stream — replace with your LLM streaming call later
    for part in ["This ", "is ", "SSE ", "streaming."]:
        yield f"data: {part}\n\n"
        await asyncio.sleep(0.15)
    yield "data: [DONE]\n\n"

@router.get("/api/stream")
async def sse_stream(prompt: str):
    return StreamingResponse(token_generator(prompt), media_type="text/event-stream")
