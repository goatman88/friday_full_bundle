Param(
  [string]$ApiBase = "http://localhost:8000",
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
& "$PSScriptRoot\env.ps1" -ApiBase $ApiBase | Out-Null

function Free-Port([int[]]$ports){
  foreach($p in $ports){
    Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
      ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }
  }
}

Free-Port 8000,5173

# backend
Start-Process powershell -ArgumentList "uvicorn backend.app:app --host 0.0.0.0 --port 8000"

# frontend
Start-Process powershell -ArgumentList "cd frontend; npm install; npm run dev"

if ($OpenBrowser) {
  Start-Process "http://localhost:5173"
}





