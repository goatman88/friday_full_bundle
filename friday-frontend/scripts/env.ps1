param([switch]$InstallFrontend = $true)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
if ($InstallFrontend) {
  Push-Location frontend
  if (Test-Path "package-lock.json") { npm ci } else { npm i }
  Pop-Location
}
Write-Host "✅ Environment ready." -ForegroundColor Green
