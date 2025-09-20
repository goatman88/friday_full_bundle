from fastapi import FastAPI, APIRouter

app = FastAPI(title="Friday API")

# simple root – optional
@app.get("/")
def root():
    return {"ok": True}

# --- API router mounted at /api ---
api = APIRouter()

@api.get("/health")
def health():
    return {"status": "ok"}

app.include_router(api, prefix="/api")






