# creates/updates all files needed; safe to re-run
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 2>$null; Set-Location .. 2>$null

# ensure folders
@("backend","frontend","scripts") | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# ----- backend files -----
$backendInit = ""
Set-Content -Path "backend\__init__.py" -Value $backendInit -Encoding UTF8

$backendApp = @'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Friday Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskIn(BaseModel):
    q: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/ask")
def ask(body: AskIn):
    return {"answer": f"You asked: {body.q}"}

@app.post("/api/session")
def session():
    return {
        "id": "local",
        "models": {"voice": "avery", "text": "gpt-4o-mini"},
        "apiBase": "http://localhost:8000",
    }
'@
Set-Content -Path "backend\app.py" -Value $backendApp -Encoding UTF8

$backendReq = @'
fastapi==0.116.2
uvicorn[standard]==0.30.6
pydantic==2.11.3
'@
Set-Content -Path "backend\requirements.txt" -Value $backendReq -Encoding UTF8

# ----- frontend proxy (vite) -----
$viteConfig = @'
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
  build: { outDir: "dist" },
});
'@
Set-Content -Path "frontend\vite.config.js" -Value $viteConfig -Encoding UTF8

# ensure vite exists in package.json (create minimal if missing)
$pkgPath = "frontend\package.json"
if (-not (Test-Path $pkgPath)) {
  $pkgJson = @'
{
  "name": "friday-frontend",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "vite": "^5.4.0"
  }
}
'@
  Set-Content -Path $pkgPath -Value $pkgJson -Encoding UTF8
}

# ----- render.yaml -----
$renderYaml = @'
services:
  - type: web
    name: friday-backend
    env: python
    rootDir: .
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn backend.app:app --host 0.0.0.0 --port $PORT

  - type: static
    name: friday-frontend
    rootDir: .
    buildCommand: bash -lc "cd frontend && (npm ci || npm i) && npm run build"
    staticPublishPath: frontend/dist
'@
Set-Content -Path "render.yaml" -Value $renderYaml -Encoding UTF8

# ----- helper scripts -----
$envPs1 = @'
param([switch]$InstallFrontend = $true)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
if ($InstallFrontend) {
  Push-Location frontend
  if (Test-Path "package-lock.json") { npm ci } else { npm i }
  Pop-Location
}
Write-Host "✅ Environment ready." -ForegroundColor Green
'@
Set-Content -Path "scripts\env.ps1" -Value $envPs1 -Encoding UTF8

$goBackend = @'
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
'@
Set-Content -Path "scripts\go-backend.ps1" -Value $goBackend -Encoding UTF8

$goFrontend = @'
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..\frontend
npm run dev
'@
Set-Content -Path "scripts\go-frontend.ps1" -Value $goFrontend -Encoding UTF8

$devRun = @'
param([switch]$OpenBrowser)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
.\scripts\env.ps1 | Out-Null
Start-Process pwsh -ArgumentList "-NoExit","-Command",".\scripts\go-backend.ps1"
Start-Sleep -Seconds 2
Push-Location frontend
npm run dev
Pop-Location
if ($OpenBrowser) { Start-Process "http://localhost:5173" }
'@
Set-Content -Path "scripts\dev-run.ps1" -Value $devRun -Encoding UTF8

$testLocal = @'
# sanity checks
try {
  $s = iwr http://localhost:8000/health -UseBasicParsing
  "GET /health => $($s.StatusCode)"
} catch { "health failed: $($_.Exception.Message)" }
$body = @{ q = "ping" } | ConvertTo-Json
try {
  $r = iwr http://localhost:8000/api/ask -Method Post -ContentType "application/json" -Body $body -UseBasicParsing
  "POST /api/ask => $($r.StatusCode) $($r.Content)"
} catch { "ask failed: $($_.Exception.Message)" }
'@
Set-Content -Path "scripts\test-local.ps1" -Value $testLocal -Encoding UTF8

# ---- install deps & quick smoke test (optional) ----
Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
Set-ExecutionPolicy -Scope Process Bypass -Force | Out-Null
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Push-Location frontend
if (Test-Path "package-lock.json") { npm ci } else { npm i }
Pop-Location

Write-Host "`n✅ Files written. You can now run:" -ForegroundColor Green
Write-Host "   .\scripts\dev-run.ps1 -OpenBrowser" -ForegroundColor Yellow
