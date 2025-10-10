# backend/app.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, platform

# --------------------------------------------------
# App
# --------------------------------------------------
app = FastAPI(
    title="Friday Backend",
    version=os.getenv("RELEASE", "0.1.0"),
)

# --------------------------------------------------
# CORS (accept FRONTEND_ORIGIN or allow all)
#   - Set FRONTEND_ORIGIN on Render to your site URL if you want to restrict.
#   - Example: https://friday-full-bundle.onrender.com
# --------------------------------------------------
_env_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]
_allow_all = not _env_origins or "*" in _env_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://friday-full-bundle.onrender.com", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Models
# --------------------------------------------------
class EchoIn(BaseModel):
    msg: str

# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/time")
def server_time():
    return {"epoch_ms": int(time.time() * 1000)}

@app.get("/api/version")
def version():
    # value mirrors FastAPI app.version (from RELEASE env)
    return {"version": app.version}

@app.post("/api/echo")
def echo(body: EchoIn, request: Request):
    return {
        "msg": body.msg,
        "client": request.client.host if request.client else None,
        "server": platform.node(),
    }

@app.get("/api/env")
def env():
    # Handy debug endpoint (remove or protect later)
    keys = ["ENV", "RELEASE", "FRONTEND_ORIGIN", "PORT"]
    return {k: os.getenv(k) for k in keys}

# Optional local runner (Render ignores this)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
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

@app.get("/")
def root(): return {"ok": True, "service": "backend"}

@app.post("/api/echo")
def echo(body: EchoIn, request: Request):
    return {
        "msg": body.msg,
        "client": request.client.host if request.client else None,
        "server": platform.node(),
    }

