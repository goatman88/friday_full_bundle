<#
Usage examples:
  pwsh -File scripts\bootstrap.ps1 -Repo https://github.com/you/friday_full_bundle.git -Branch main -Dest C:\work\friday-frontend
If you run it from an empty folder, it will clone into that folder by default.
#>
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [string]$Branch = "main",
  [string]$Dest = (Get-Location).Path
)
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process Bypass -Force | Out-Null

if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Force -Path $Dest | Out-Null }
Set-Location $Dest

# Clone if the folder is empty or not a git repo
if (-not (Test-Path ".git")) {
  git clone --branch $Branch $Repo . 
}

# Ensure scripts folder exists, then drop apply-fixes & render-update if missing (so re-runs work)
if (-not (Test-Path "scripts")) { New-Item -ItemType Directory scripts | Out-Null }

# If apply-fixes.ps1 is not present (fresh repo), create it quickly by downloading from current script memory:
if (-not (Test-Path "scripts\apply-fixes.ps1")) {
  Write-Host "Please paste scripts\apply-fixes.ps1 first (from the chat). Aborting." -ForegroundColor Yellow
  exit 1
}

# Apply fixes
.\scripts\apply-fixes.ps1

# Quick local check (optional)
Start-Process pwsh -ArgumentList "-NoExit","-Command",".\scripts\go-backend.ps1"
Start-Sleep -Seconds 2
try { iwr http://localhost:8000/health -UseBasicParsing | Out-Null } catch {}
# Don’t block; stop here and let user run dev-run for full FE+BE

# Push to trigger Render
if (Test-Path "scripts\render-update.ps1") {
  .\scripts\render-update.ps1
} else {
  Write-Host "⚠️ scripts\render-update.ps1 not found; skipping push." -ForegroundColor Yellow
}
