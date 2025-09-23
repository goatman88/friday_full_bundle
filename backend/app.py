from fastapi import FastAPI
from backend.history import router as history_router

app = FastAPI()
app.include_router(history_router)
