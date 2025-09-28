param([switch]$InstallFrontend = $true)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root

if (-not (Test-Path ".\.venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip | Out-Null
pip install -r backend\requirements.txt

if ($InstallFrontend) {
  Push-Location frontend
  if (Test-Path "package-lock.json") { npm ci } else { npm i }
  Pop-Location
}
Write-Host "✅ Environment ready." -ForegroundColor Green
