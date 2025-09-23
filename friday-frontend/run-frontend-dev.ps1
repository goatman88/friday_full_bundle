param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Kill any leftovers on 5173
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }

# node deps
if (-not (Test-Path ".\node_modules")) { npm ci } else { npm install }

Write-Host ">>> Starting FRONTEND on port 5173..." -ForegroundColor Cyan
npm run dev
