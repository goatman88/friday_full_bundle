# scripts/dev-run.ps1
[CmdletBinding()]
Param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

function Kill-Port([int]$port) {
  Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }
}

Write-Host ">>> Cleaning ports $FrontendPort and $BackendPort..." -ForegroundColor Yellow
Kill-Port $FrontendPort
Kill-Port $BackendPort

# Make sure env is set
if (-not $env:VITE_API_BASE) {
  . "$PSScriptRoot\env.ps1"
}

# Start backend
Write-Host ">>> Starting BACKEND on :$BackendPort..." -ForegroundColor Cyan
$backendCmd = "uvicorn backend.app:app --host 0.0.0.0 --port $BackendPort --reload"
Start-Process pwsh -ArgumentList "-NoExit","-Command",$backendCmd

Start-Sleep -Seconds 1

# Start frontend
Write-Host ">>> Starting FRONTEND on :$FrontendPort..." -ForegroundColor Cyan
$frontCmd = "npm run dev"
Start-Process pwsh -ArgumentList "-NoExit","-Command",$frontCmd

# Probe health
Start-Sleep -Seconds 2
$api  = $env:VITE_API_BASE
$ui   = "http://localhost:$FrontendPort"
function Test-Health($u) { try { (Invoke-WebRequest -Uri $u -UseBasicParsing).StatusCode -eq 200 } catch { $false } }

$h1 = Test-Health("$api/health")
$h2 = Test-Health("$api/api/health")
$h3 = Test-Health("$ui/health")
$h4 = Test-Health("$ui/api/health")

if ($h1 -and $h2 -and $h3 -and $h4) {
  Write-Host "`nOK ✅  Both backend and frontend health are green." -ForegroundColor Green
  if ($OpenBrowser) { Start-Process "$ui" }
} else {
  Write-Host "`nSomething is off. Check the two windows." -ForegroundColor Magenta
  "`nBackend health ($api/health): $h1"
  "Backend API health ($api/api/health): $h2"
  "Frontend /health ($ui/health): $h3"
  "Frontend /api/health ($ui/api/health): $h4" | ForEach-Object { Write-Host $_ }
}

