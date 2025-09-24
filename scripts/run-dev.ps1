# scripts/run-dev.ps1
param([switch]$OpenBrowser)

Write-Host "Setting environment variables..." -ForegroundColor Cyan
.\scripts\env.ps1

Write-Host "Starting backend + frontend..." -ForegroundColor Cyan
if ($OpenBrowser) {
    .\scripts\dev-run.ps1 -OpenBrowser
} else {
    .\scripts\dev-run.ps1
}
