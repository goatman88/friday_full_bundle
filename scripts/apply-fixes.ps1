# Idempotent: safe to re-run. Writes/repairs backend, frontend, render files.
# Run from anywhere; it will hop to repo root automatically.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
Set-Location ..

function Ensure-Folder($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

Ensure-Folder "backend"
Ensure-Folder "frontend"
Ensure-Folder "scripts"

# --- Backend files ---
Set-Content backend\__init__.py -Value "" -Encoding UTF8

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
Set-Content backend\app.py -Value $backendApp -Encoding UTF8

$req = @'
fastapi==0.116.2
uvicorn[standard]==0.30.6
pydantic==2.11.3
'@
Set-Content backend\requirements.txt -Value $req -Encoding UTF8

# --- Frontend files ---
# Minimal package.json to guarantee vite is available, even if your project didn’t have one.
$pkgPath = "frontend\package.json"
if (-not (Test-Path $pkgPath)) {
  $pkg = @'
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
  Set-Content $pkgPath -Value $pkg -Encoding UTF8
}

$viteCfg = @'
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/api": "http://localhost:8000"
    }
  },
  build: { outDir: "dist" }
});
'@
Set-Content frontend\vite.config.js -Value $viteCfg -Encoding UTF8

# --- Render config ---
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
Set-Content render.yaml -Value $renderYaml -Encoding UTF8

# --- Helper scripts (call other scripts by path-anchoring to repo root) ---
$envBlock = @'
param([switch]$InstallFrontend = $true)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root

if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip | Out-Null
pip install -r backend\requirements.txt

if ($InstallFrontend) {
  Push-Location frontend
  if (Test-Path "package-lock.json") { npm ci } else { npm i }
  Pop-Location
}
Write-Host "✅ Environment ready." -ForegroundColor Green
'@
Set-Content scripts\env.ps1 -Value $envBlock -Encoding UTF8

$goBackend = @'
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = $root
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
'@
Set-Content scripts\go-backend.ps1 -Value $goBackend -Encoding UTF8

$goFrontend = @'
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location "$root\frontend"
# If vite isn’t installed yet, install dependencies once:
if (-not (Test-Path "node_modules")) { if (Test-Path "package-lock.json") { npm ci } else { npm i } }
# If 5173 is busy, Vite will auto-prompt to use a new port; allow it.
npm run dev
'@
Set-Content scripts\go-frontend.ps1 -Value $goFrontend -Encoding UTF8

$testLocal = @'
$ErrorActionPreference = "Continue"
function Hit($label,$url,$method="GET",$body=$null){
  try {
    if ($method -eq "GET") {
      $r = iwr $url -UseBasicParsing
    } else {
      $r = iwr $url -Method Post -ContentType "application/json" -Body $body -UseBasicParsing
    }
    Write-Host "[$label] $url => $($r.StatusCode) $($r.Content)"
  } catch {
    Write-Host "[$label] ERROR $url => $($_.Exception.Message)" -ForegroundColor Red
  }
}
Hit "health" "http://localhost:8000/health"
$body = @{ q = "ping" } | ConvertTo-Json
Hit "ask" "http://localhost:8000/api/ask" "POST" $body
Hit "session" "http://localhost:8000/api/session" "POST" "{}"
'@
Set-Content scripts\test-local.ps1 -Value $testLocal -Encoding UTF8

$devRun = @'
param([switch]$OpenBrowser)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root

# Free ports if needed (Windows)
$ports = @(5173,8000)
foreach ($p in $ports) {
  $pids = (Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) 2>$null
  foreach ($pid in $pids) { try { Stop-Process -Id $pid -Force } catch {} }
}

# Prepare env
Set-ExecutionPolicy -Scope Process Bypass -Force | Out-Null
.\scripts\env.ps1 | Out-Null

# Start backend in new window
Start-Process pwsh -ArgumentList "-NoExit","-Command",".\scripts\go-backend.ps1"
Start-Sleep -Seconds 2

# Wait for backend /health (10s max)
$ok=$false
for ($i=0; $i -lt 20; $i++) {
  try { $s = iwr http://localhost:8000/health -UseBasicParsing; if ($s.StatusCode -eq 200) { $ok=$true; break } } catch {}
  Start-Sleep -Milliseconds 500
}
if (-not $ok) { Write-Host "⚠️ Backend health not ready yet, continuing..." -ForegroundColor Yellow }

# Start frontend (current window)
Push-Location frontend
npm run dev
Pop-Location

if ($OpenBrowser) { Start-Process "http://localhost:5173" }
'@
Set-Content scripts\dev-run.ps1 -Value $devRun -Encoding UTF8

$renderPush = @'
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root
git add backend frontend render.yaml scripts
git commit -m "apply fixes: backend app, vite proxy, render.yaml, helper scripts" 2>$null
git push origin main
Write-Host "📤 Pushed to origin/main. Render should redeploy now." -ForegroundColor Green
'@
Set-Content scripts\render-update.ps1 -Value $renderPush -Encoding UTF8

Write-Host "`n✅ Files written/updated. Next:" -ForegroundColor Green
Write-Host "   Set-ExecutionPolicy -Scope Process Bypass -Force"
Write-Host "   .\scripts\dev-run.ps1 -OpenBrowser"
