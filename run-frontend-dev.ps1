# Requires: Node.js 18+ on PATH
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSCommandPath
Set-Location $here

# 1) .env.local
$envFile = ".\.env.local"
if (-not (Test-Path $envFile)) {
  @"
VITE_API_BASE=http://localhost:8000
PICOVOICE_ACCESS_KEY=PUT-YOUR-REAL-KEY-HERE
"@ | Set-Content -Encoding UTF8 $envFile
  Write-Host "Created .env.local (edit PICOVOICE_ACCESS_KEY later if needed)." -ForegroundColor Yellow
}

# 2) deps
if (-not (Test-Path .\node_modules)) {
  Write-Host "Installing frontend deps (npm ci) ..." -ForegroundColor Yellow
  if (Test-Path .\package-lock.json) { npm ci } else { npm install }
}

# 3) run vite
Write-Host "Starting Vite on http://localhost:5173 ..." -ForegroundColor Green
npm run dev

