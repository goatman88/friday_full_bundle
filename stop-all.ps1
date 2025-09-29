# stop-all.ps1
Get-NetTCPConnection -LocalPort 8000,5173,5174 -ErrorAction SilentlyContinue |
  Select-Object -Expand OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force } 2>$null
