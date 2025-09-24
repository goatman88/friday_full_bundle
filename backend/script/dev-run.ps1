Param(
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

# 1) set env + free ports
& "$PSScriptRoot\env.ps1"

# 2) start backend (from backend dir) in a new window
Start-Process powershell -ArgumentList "-NoExit","-Command",
  "& `"$PSScriptRoot\go-backend.ps1`"; python -m pip install -r requirements.txt; uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

# 3) start frontend (from project root) in a new window
$proj = (Resolve-Path "$PSScriptRoot\..").Path
Start-Process powershell -ArgumentList "-NoExit","-Command",
  "Set-Location `"$proj`"; if (Test-Path package.json) { npm install; npm run dev } else { Write-Host 'No package.json here; open your frontend window manually.' }"

# 4) optional: open frontend
if ($OpenBrowser) { Start-Process "http://localhost:5173" }



