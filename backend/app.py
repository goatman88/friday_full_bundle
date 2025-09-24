from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday Backend", version="0.1.0")

# Allow local dev & Render frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def root_health():
    return {"status": "ok"}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}

@app.post("/api/ask")
def ask(payload: dict = Body(...)):
    # Expect {"q": "..."}  (earlier 422s came from sending {"prompt": "..."}).
    q = payload.get("q", "").strip()
    if not q:
        return {"error": "missing field 'q'"}
    # Phase 1: echo – replace with model call later
    return {"answer": f"You asked: {q}"}

@app.post("/api/session")
def session():
    # Phase 2 will return ids/models/etc.; for now just confirm it exists
    return {"session": "ok"}















