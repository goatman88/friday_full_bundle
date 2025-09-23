<# 
fix-dev.ps1
Runs sanity checks, kills busy ports, exports Vite envs, and starts both windows.
Usage:
  pwsh -f .\fix-dev.ps1 -ApiBase "http://localhost:8000" -OpenBrowser
#>

[CmdletBinding()]
param(
  [string]$ApiBase = "http://localhost:8000",
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$PSStyle.OutputRendering = "PlainText"

function Say($t,[ConsoleColor]$c="Green"){ $orig=[Console]::ForegroundColor; [Console]::ForegroundColor=$c; Write-Host $t; [Console]::ForegroundColor=$orig }

# 0) Sanity: ensure we’re in the project root
$root = (Get-Location).Path
$frontend = Join-Path $root "friday-frontend"
$backend  = Join-Path $root "backend"
if(!(Test-Path $frontend)){ throw "Missing $frontend" }
if(!(Test-Path $backend )){ throw "Missing $backend"  }

# 1) Kill ports
Say "Killing anything on :5173 and :8000..." "Yellow"
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue | %{
  try{ Stop-Process -Id $_.OwningProcess -Force }catch{}
}

# 2) Ensure frontend env and vite proxy work
Say "Setting Vite env…" "Yellow"
$env:VITE_API_BASE = $ApiBase
$env:VITE_SESSION_ID = "local-dev"

# 3) Backend venv + deps (idempotent)
Push-Location $root
if(!(Test-Path ".venv")){
  Say "Creating .venv…" "Yellow"
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -r "$backend\requirements.txt"

# 4) Start BACKEND (new window)
Say "Starting backend on :8000…" "Cyan"
$backendCmd = "cd `"$root`"; .\.venv\Scripts\Activate.ps1; uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"
Start-Process pwsh -ArgumentList "-NoExit","-Command",$backendCmd | Out-Null

# 5) Frontend install if needed
Push-Location $frontend
if(!(Test-Path "node_modules")){
  Say "Installing frontend deps…" "Yellow"
  npm ci
}

# 6) Start FRONTEND (new window)
Say "Starting frontend on :5173…" "Cyan"
$frontCmd = "cd `"$frontend`"; `$env:VITE_API_BASE=`"$ApiBase`"; npm run dev"
Start-Process pwsh -ArgumentList "-NoExit","-Command",$frontCmd | Out-Null
Pop-Location

# 7) Verify both healths
Start-Sleep -Seconds 2
$ok1 = try{ (iwr "http://localhost:8000/health").StatusCode -eq 200 }catch{ $false }
$ok2 = try{ (iwr "http://localhost:5173/health").StatusCode -eq 200 }catch{ $false }
if($ok1 -and $ok2){ Say "OK: both health checks are green." "Green" } else { Say "Something is off. Check the two new windows." "Magenta" }

if($OpenBrowser){ Start-Process "http://localhost:5173" }
