from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/chat")
async def chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            # echo for now — swap in your model call or router here
            await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        pass

