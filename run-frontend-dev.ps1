# --- run-frontend-dev.ps1 ---
$ErrorActionPreference = 'Stop'

# 1) Find repo root where package.json lives
$here = Get-Location
$root = $null
$roots = @(
  $here,
  (Join-Path $HOME 'friday-frontend\friday-frontend'),
  (Join-Path $HOME 'friday-frontend')
)
foreach ($r in $roots) {
  if (Test-Path $r) {
    if (Test-Path (Join-Path $r 'package.json')) { $root = $r; break }
  }
}
if (-not $root) { throw "Could not locate repo root (no package.json)." }

Set-Location $root
Write-Host "Repo root: $((Get-Location).Path)" -ForegroundColor Green

# 2) Install deps cleanly (fixes the “Internal Server Error… vite chunk” issue)
if (Test-Path node_modules) { Remove-Item node_modules -Recurse -Force }
if (Test-Path package-lock.json) { Remove-Item package-lock.json -Force }
npm cache verify | Out-Null
npm ci

# 3) Point Vite to backend
$env:VITE_API_BASE = "http://localhost:8000"

# 4) Run dev server on 5173; use npx so “vite not recognized” can’t happen
Write-Host ">>> Starting FRONTEND on port 5173..." -ForegroundColor Cyan
npx vite --host --port 5173


