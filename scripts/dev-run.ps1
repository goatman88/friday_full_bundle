# scripts/dev-run.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\..\

# 0) Load env and clear ports
.\scripts\env.ps1
.\scripts\fix-ports.ps1

# 1) Backend (ensure requirements are installed)
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# 2) Start backend in a new window
$backendCmd = "cmd /c `"cd /d `"$((Get-Location).Path)`" && .\.venv\Scripts\Activate.ps1 && uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload`""
Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd
Start-Sleep -Seconds 2

# 3) Frontend deps + dev
npm install
$frontCmd = "cmd /c `"cd /d `"$((Get-Location).Path)`" && npm run dev`""
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontCmd

# 4) Quick local health check
function Hit([string]$u) {
  try { (Invoke-WebRequest -Uri $u -UseBasicParsing).StatusCode } catch { $_.Exception.Response.StatusCode.value__ }
}
Write-Host "`nLocal checks:" -ForegroundColor Yellow
" http://localhost:8000/health  -> $(Hit "http://localhost:8000/health")"
" http://localhost:5173/        -> open in browser"

Pop-Location
