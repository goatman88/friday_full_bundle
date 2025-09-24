Param([switch]$OpenBrowser)

# kill 5173 and 8000
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }

# start backend (from backend dir)
Start-Process powershell -ArgumentList "-NoExit","-Command","cd backend; ..\.venv\Scripts\Activate.ps1; uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

# start frontend (from frontend root)
Start-Process powershell -ArgumentList "-NoExit","-Command","npm run dev -- --port 5173"

if ($OpenBrowser) { Start-Process "http://localhost:5173" }



