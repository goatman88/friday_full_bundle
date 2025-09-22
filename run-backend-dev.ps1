# Requires: Python 3.10+ on PATH
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSCommandPath
Set-Location $here

# 1) venv
if (-not (Test-Path .\.venv)) { 
  Write-Host "Creating venv..." -ForegroundColor Yellow
  python -m venv .venv
}
$venvPy = Join-Path .\.venv\Scripts python.exe
$pip    = "$venvPy -m pip"

# 2) deps
Write-Host "Installing backend deps..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r backend/requirements.txt

# 3) run uvicorn
$env:PYTHONUNBUFFERED = "1"
$port = 8000
Write-Host "Starting backend on http://localhost:$port ..." -ForegroundColor Green
& $venvPy -m uvicorn backend.app.app:app --host 0.0.0.0 --port $port --reload

