param([switch]$OpenBrowser)

# Kill stuck ports
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }

# Start backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn backend.main:app --reload --port 8000"

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

# Open browser
if ($OpenBrowser) {
  Start-Process "http://localhost:5173"
}


