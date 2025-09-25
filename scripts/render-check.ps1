param([ValidateSet("root","backend")]$ServiceRoot="root")

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $root
. .\.venv\Scripts\Activate.ps1

if ($ServiceRoot -eq "backend") {
  Write-Host "Simulating Render with service root = /backend"
  Set-Location backend
  uvicorn app:app --host 0.0.0.0 --port 8000
} else {
  Write-Host "Simulating Render with service root = repo root"
  Set-Location $root
  uvicorn backend.app:app --host 0.0.0.0 --port 8000
}



