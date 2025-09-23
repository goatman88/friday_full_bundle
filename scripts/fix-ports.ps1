# scripts/fix-ports.ps1
param(
  [int[]]$Ports = @(5173, 8000)
)
$ErrorActionPreference = "SilentlyContinue"

foreach ($p in $Ports) {
  Get-NetTCPConnection -LocalPort $p | ForEach-Object {
    try {
      Stop-Process -Id $_.OwningProcess -Force
      Write-Host "Killed PID $($_.OwningProcess) on port $p" -ForegroundColor Magenta
    } catch {}
  }
}
Write-Host "Ports cleared." -ForegroundColor Green
