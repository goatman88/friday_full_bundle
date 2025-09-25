param([switch]$OpenBrowser)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
.\scripts\env.ps1 | Out-Null
Start-Process pwsh -ArgumentList "-NoExit","-Command",".\scripts\go-backend.ps1"
Start-Sleep -Seconds 2
Push-Location frontend
npm run dev
Pop-Location
if ($OpenBrowser) { Start-Process "http://localhost:5173" }
