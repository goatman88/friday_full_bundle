Param([switch]$OpenBrowser)

# 0) Make sure we’re in backend folder that contains app.py
if (-not (Test-Path -Path "./app.py")) {
  Write-Error "Run this from the folder that contains app.py (backend/)."
  exit 1
}

# 1) Free ports we use locally
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }

# 2) Start backend (uvicorn app:app)
Start-Process powershell -ArgumentList 'uvicorn app:app --host 0.0.0.0 --port 8000 --reload'

# 3) Start frontend from repo root (one level up)
$repoRoot = (Resolve-Path "..").Path
Start-Process powershell -ArgumentList "cd `"$repoRoot`"; npm run dev"

# 4) Optionally open browser
if ($OpenBrowser) { Start-Process "http://localhost:5173" }


