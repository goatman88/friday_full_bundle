Param(
  [Parameter(Mandatory=$false)][string]$ApiBase = "http://localhost:8000"
)

$env:VITE_API_BASE = $ApiBase
$env:FRI_BACKEND_URL = $ApiBase

Write-Host "Environment set:" -ForegroundColor Green
Write-Host ("  Backend : {0}" -f $env:FRI_BACKEND_URL)
Write-Host ("  Frontend: http://localhost:5173")

