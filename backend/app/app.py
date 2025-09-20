from fastapi import FastAPI
from .health import health_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

app.include_router(health_router, prefix='/api')
@app.get('/health', tags=['meta'])
async def _health_root():
    return {'status': 'ok'}
