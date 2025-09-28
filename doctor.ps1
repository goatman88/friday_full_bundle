# doctor.ps1
Write-Host "== Doctor Check ==" -ForegroundColor Cyan
python --version
node -v; npm -v

if (-not (Test-Path backend/app.py)) { Write-Host "Backend missing app.py" -ForegroundColor Red; exit 1 }
if (-not (Test-Path frontend/package.json)) { Write-Host "Frontend missing package.json" -ForegroundColor Red; exit 1 }

Write-Host "OK basics exist" -ForegroundColor Green
Write-Host "Run backend: .\.venv\Scripts\Activate.ps1; pip install -r backend/requirements.txt; uvicorn backend.app:app --reload --port 8000"
Write-Host "Run frontend: cd frontend; npm install; npm run dev"
