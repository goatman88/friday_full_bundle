from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday API")

# Allow your Vite dev server and your Render static-site origin.
# You can keep "*" during bring-up and tighten later.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: We put "/api" in the *route* so Render doesn't need root_path headers.
@app.get("/api/health")
def health():
    return {"status": "ok"}

