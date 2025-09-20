from fastapi import FastAPI
from .health import router as health_router

app = FastAPI()

# Mount all API routes under /api (only here; do NOT prefix again in the router)
app.include_router(health_router, prefix="/api")


# Optional root for quick sanity (not required)
@app.get("/")
def root():
    return {"ok": True}






