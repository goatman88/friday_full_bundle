# run-backend-dev.ps1
$ErrorActionPreference = "Stop"
cd $PSScriptRoot
if (-not (Test-Path ".venv")) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
$env:PYTHONUNBUFFERED = "1"
uvicorn backend.app.app:app --host 0.0.0.0 --port 8000 --reload
