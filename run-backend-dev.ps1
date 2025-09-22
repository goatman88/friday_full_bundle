# --- run-backend-dev.ps1 ---
$ErrorActionPreference = 'Stop'

# 1) Find repo root (directory that has package.json and the backend folder)
$here = Get-Location
$root = $null
$roots = @(
  $here,
  (Join-Path $HOME 'friday-frontend\friday-frontend'),
  (Join-Path $HOME 'friday-frontend')
)
foreach ($r in $roots) {
  if (Test-Path $r) {
    if (Test-Path (Join-Path $r 'package.json') -and (Test-Path (Join-Path $r 'backend\app\app.py'))) { $root = $r; break }
  }
}
if (-not $root) { throw "Could not locate repo root (no package.json + backend\app\app.py)." }

Set-Location $root
Write-Host "Repo root: $((Get-Location).Path)" -ForegroundColor Green

# 2) Python venv
if (-not (Test-Path ".venv")) {
  Write-Host "Creating venv..." -ForegroundColor Yellow
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

# 3) Deps
pip install -r backend\requirements.txt

# 4) Environment (frontend will proxy to backend on 8000)
$env:PYTHONUNBUFFERED = "1"

# 5) Run FastAPI (***important fix*** module path)
Write-Host ">>> Starting BACKEND on port 8000..." -ForegroundColor Cyan
uvicorn backend.app.app:app --host 0.0.0.0 --port 8000 --reload


