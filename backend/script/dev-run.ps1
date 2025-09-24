Param(
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

# 1) Kill anything on 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }
Write-Host "✅ Freed port 8000"

# 2) Activate venv if present
if (Test-Path .\.venv\Scripts\Activate.ps1) {
  & .\.venv\Scripts\Activate.ps1
  Write-Host "✅ venv activated"
} else {
  Write-Host "ℹ️  No venv found; using global python." -ForegroundColor Yellow
}

# 3) Install deps (idempotent)
pip install -r requirements.txt | Out-Null
Write-Host "✅ requirements installed"

# 4) Run Uvicorn (from backend folder!)
$pwdPath = (Get-Location).Path
if (-not ($pwdPath -like "*\backend")) {
  Set-Location backend
}
Write-Host "🚀 Starting backend at http://localhost:8000 ..."
Start-Process powershell -ArgumentList "uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

# 5) Optional quick checks
Start-Sleep -Seconds 1
try {
  $r1 = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
  $r2 = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing
  Write-Host "/health     :" $r1.StatusCode
  Write-Host "/api/health :" $r2.StatusCode
} catch {
  Write-Host "Health checks failed (backend may still be starting):" $_.Exception.Message -ForegroundColor Yellow
}

if ($OpenBrowser) {
  Start-Process "http://localhost:8000/health"
}
