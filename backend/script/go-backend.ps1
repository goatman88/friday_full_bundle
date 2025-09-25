Param([switch]$OpenBrowser)
$ErrorActionPreference = "Stop"

$env:API_BASE = "http://localhost:8000"

# free dev ports
foreach ($p in 5173,8000) {
  Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Write-Host "Environment set. API_BASE=$($env:API_BASE)"
Write-Host "Freed ports 5173, 8000" -ForegroundColor Green

if ($OpenBrowser) { Start-Process "http://localhost:5173" }

