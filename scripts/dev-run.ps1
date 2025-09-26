param([switch]$OpenBrowser)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root

# Ensure venv is active
if (-not (Test-Path ".venv")) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1

# Kill anything on 8000/5173 (optional)
Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'node|uvicorn' } | Stop-Process -Force -ErrorAction SilentlyContinue | Out-Null

# Start backend (repo root => backend.app:app)
$be = Start-Process pwsh -PassThru -ArgumentList @(
  "-NoExit","-Command","Set-Location '$root'; uvicorn backend.app:app --host 0.0.0.0 --port 8000"
)

Start-Sleep 2

# Start frontend
$fe = Start-Process pwsh -PassThru -ArgumentList @(
  "-NoExit","-Command","Set-Location '$root\frontend'; npm run dev"
)

if ($OpenBrowser) { Start-Process http://localhost:5173 }

Write-Host "Dev servers launching. Backend : http://localhost:8000 | Frontend : http://localhost:5173"







