Write-Host "Update Render Web Service:" -ForegroundColor Yellow
Write-Host "Build Command : pip install -r backend/requirements.txt" -ForegroundColor Green
Write-Host "Start  Command : uvicorn backend.app.app:app --host 0.0.0.0 --port `$PORT" -ForegroundColor Green