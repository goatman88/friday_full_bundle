from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, platform

app = FastAPI(title="Friday Backend", version=os.getenv("RELEASE", "0.1.0"))

allowed_origins = [
    os.getenv("FRONTEND_ORIGIN", ""),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in allowed_origins if o] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/time")
def server_time():
    return {"epoch_ms": int(time.time() * 1000)}

@app.get("/api/version")
def version():
    return {"version": app.version}

class EchoIn(BaseModel):
    msg: str

@app.post("/api/echo")
def echo(body: EchoIn, request: Request):
    return {
        "msg": body.msg,
        "client": request.client.host if request.client else None,
        "server": platform.node(),
    }
