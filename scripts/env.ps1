# scripts/env.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Set-Var([string]$name, [string]$value) {
  if ([string]::IsNullOrWhiteSpace($value)) { return }
  [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
  Write-Host "set $name=$value" -ForegroundColor Cyan
}

# Load .env.local if it exists (KEY=VALUE per line)
$envFile = Join-Path (Get-Location) ".env.local"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*$') { return }
    $k, $v = $_ -split '=', 2
    if ($k -and $v) { Set-Var $k.Trim() $v.Trim() }
  }
  Write-Host "Loaded .env.local" -ForegroundColor Green
}

# Ask (once) for your deployed Render URLs (or keep existing)
if (-not $env:FRI_BACKEND_URL) {
  $b = Read-Host "Paste your Render BACKEND base URL (e.g. https://friday-xxxx.onrender.com). Leave blank for local http://localhost:8000"
  if ([string]::IsNullOrWhiteSpace($b)) { $b = "http://localhost:8000" }
  Set-Var "FRI_BACKEND_URL" $b
}
if (-not $env:FRI_FRONTEND_URL) {
  $f = Read-Host "Paste your Render FRONTEND URL (optional). Leave blank to skip"
  if (-not [string]::IsNullOrWhiteSpace($f)) { Set-Var "FRI_FRONTEND_URL" $f }
}

# Convenience aliases
$global:backendUrl  = $env:FRI_BACKEND_URL
$global:frontendUrl = $env:FRI_FRONTEND_URL
Write-Host "backendUrl=$backendUrl" -ForegroundColor Yellow
if ($frontendUrl) { Write-Host "frontendUrl=$frontendUrl" -ForegroundColor Yellow }
