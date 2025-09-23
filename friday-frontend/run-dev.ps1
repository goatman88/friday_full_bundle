param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# optional: clear ports
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }

Write-Host ">>> Launching Backend + Frontend..." -ForegroundColor Yellow

# start backend in its own PowerShell
Start-Process powershell -ArgumentList '-NoExit','-Command', (".\run-backend-dev.ps1")

# start frontend in its own PowerShell
Start-Process powershell -ArgumentList '-NoExit','-Command', (".\run-frontend-dev.ps1")

# quick health pings to show green
function Test-Health($u){ try { (Invoke-WebRequest -Uri $u -UseBasicParsing).StatusCode -eq 200 } catch { $false } }
Start-Sleep -Seconds 2
$u1 = "http://localhost:8000/api/health"
$u2 = "http://localhost:5173/health"
$ok1 = Test-Health $u1
$ok2 = Test-Health $u2
if($ok1 -and $ok2){ Write-Host "OK" -ForegroundColor Green } else { Write-Host "Something is off. Check the two windows." -ForegroundColor Magenta }
