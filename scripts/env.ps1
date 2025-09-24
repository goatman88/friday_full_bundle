Param(
  [string]$ApiBase = "http://localhost:8000"
)

# Let scripts run just for this shell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass | Out-Null

# Free any stuck local ports
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
}

$env:VITE_API_BASE = $ApiBase
Write-Host "`n✅ Environment set:" -ForegroundColor Green
Write-Host "  Backend : $ApiBase"
Write-Host "  Frontend: http://localhost:5173"



