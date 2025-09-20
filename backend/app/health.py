from fastapi import APIRouter

health_router = APIRouter()

@health_router.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
