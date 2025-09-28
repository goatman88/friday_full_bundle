<#  --- Friday reset & bootstrap (Windows PowerShell)
    Run from the repo root. Example:
      Set-ExecutionPolicy Bypass -Scope CurrentUser -Force
      cd $HOME\friday-frontend
      .\reset-friday.ps1 -Run   # builds everything and starts both servers
#>

param(
  [switch]$Run
)

$ErrorActionPreference = 'Stop'

# --- Helpers ---------------------------------------------------------------
function Kill-Port([int]$p){
  Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
    Select-Object -Expand OwningProcess -Unique |
    ForEach-Object { try { Stop-Process -Id $_ -Force } catch {} }
}

function Write-Ok($t){  Write-Host "OK  $t" -ForegroundColor Green }
function Write-Step($t){ Write-Host "== $t ==" -ForegroundColor Cyan }
function Write-Do($t){  Write-Host $t -ForegroundColor Yellow }

# --- Clean/Reset project ---------------------------------------------------
Write-Step "Resetting Friday project"

# stop anything on our dev ports
[int]$BackendPort  = 8000
[int]$FrontendPort = 5173
Write-Do "Stopping anything on ports $BackendPort and $FrontendPort..."
Kill-Port $BackendPort
Kill-Port $FrontendPort
Write-Ok "ports free"

# remove old trees (best-effort)
Remove-Item backend  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item frontend -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item scripts  -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Name backend  | Out-Null
New-Item -ItemType Directory -Name frontend | Out-Null
New-Item -ItemType Directory -Name scripts  | Out-Null

# --- Backend scaffold ------------------------------------------------------
Write-Step "Creating backend"

@'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

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

@app.post("/api/ask")
def ask(body: dict):
    q = (body or {}).get("q", "")
    return {"answer": f"you asked: {q}"}
'@ | Set-Content -Encoding UTF8 backend/app.py

@'
fastapi==0.116.2
uvicorn[standard]==0.30.6
'@ | Set-Content -Encoding UTF8 backend/requirements.txt

# --- Frontend scaffold -----------------------------------------------------
Write-Step "Creating frontend (Vite vanilla)"

# create fresh Vite skeleton
pushd .
cd frontend
npx --yes create-vite@latest . --template vanilla | Out-Null
npm install | Out-Null
popd

# Frontend entry that pings backend
@'
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Friday Frontend</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/main.js"></script>
  </body>
</html>
'@ | Set-Content -Encoding UTF8 frontend/index.html

@'
document.querySelector("#app").innerHTML = `
  <h1>Friday Frontend</h1>
  <button id="ping">Ping backend</button>
  <pre id="out"></pre>
`;
document.querySelector("#ping").onclick = async () => {
  const out = document.querySelector("#out");
  try {
    const r = await fetch("http://localhost:8000/api/health");
    out.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) {
    out.textContent = "Ping failed: " + e;
  }
};
'@ | Set-Content -Encoding UTF8 frontend/main.js

# make sure scripts exist in package.json
$pkg = Get-Content frontend/package.json | ConvertFrom-Json
$pkg.scripts.dev   = "vite"
$pkg.scripts.build = "vite build"
$pkg.scripts.preview = "vite preview --port 5173"
$pkg | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 frontend/package.json

Write-Ok "backend & frontend created"

# --- Python venv & deps ----------------------------------------------------
Write-Step "Python venv & deps"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip > $null
pip install -r backend/requirements.txt > $null
Write-Ok "pip deps installed"

# --- Local run -------------------------------------------------------------
if ($Run) {
  Write-Step "Starting servers"

  # start backend
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$PWD'; .\.venv\Scripts\Activate.ps1; uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"

  Start-Sleep -Seconds 2

  # start frontend
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$PWD\frontend'; npm run dev"

  Write-Do "Open:"
  Write-Host "  http://localhost:8000/api/health   (backend health)" -ForegroundColor White
  Write-Host "  http://localhost:5173/             (Vite dev)" -ForegroundColor White
}
