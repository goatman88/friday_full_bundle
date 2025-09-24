Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass | Out-Null
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
cd "$root\backend"

if (-Not (Test-Path ".venv")) {
  python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "⏳ Starting backend on :8000 ..." -ForegroundColor Yellow
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
