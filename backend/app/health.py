from fastapi import APIRouter

# No prefix here. We mount the prefix in app.py.
router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}
