param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Kill any leftovers on 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }

# venv
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1

# deps
pip install -r backend\requirements.txt

# make imports like "import backend.something" work
$env:PYTHONPATH = (Get-Location).Path

Write-Host ">>> Starting BACKEND on port 8000..." -ForegroundColor Cyan
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
