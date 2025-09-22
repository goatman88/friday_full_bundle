# run-dev.ps1
Write-Host ">>> Launching Backend + Frontend..." -ForegroundColor Yellow

# Start backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\Activate.ps1; uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

