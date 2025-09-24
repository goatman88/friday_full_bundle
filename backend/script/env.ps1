# Set dev URLs and free common dev ports
$env:FRI_BACKEND_URL = "http://localhost:8000"
$env:FRI_FRONTEND_URL = "http://localhost:5173"

# free ports 5173, 8000 if anything is stuck
$ports = 5173,8000
foreach ($p in $ports) {
  Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
    ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }
}
Write-Host "Environment set:`n  Backend : $($env:FRI_BACKEND_URL)`n  Frontend: $($env:FRI_FRONTEND_URL)"


