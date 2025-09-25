Param(
  [string]$ApiBase = "http://localhost:8000",
  [switch]$Print=$true
)

$ErrorActionPreference = "Stop"

$script:Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $script:Root

# show where we are
if ($Print) {
  Write-Host "Repo root:" $script:Root -ForegroundColor Green
}

# helpful envs for Python imports
$env:PYTHONPATH = $script:Root

# print service endpoints
if ($Print) {
  Write-Host "Backend : $ApiBase" -ForegroundColor Cyan
  Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
}




