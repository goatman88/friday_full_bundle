$ports = 5173,8000
Get-Process -Id (Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue).OwningProcess `
  -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "✅ Freed ports $($ports -join ', ')"
