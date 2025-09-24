Param([string]$ApiBase = "http://localhost:8000", [string]$Port = "5173")
$env:VITE_API_BASE = $ApiBase
Write-Host "Environment set:"
Write-Host ("  Backend : {0}" -f $env:VITE_API_BASE)
Write-Host ("  Frontend: http://localhost:{0}" -f $Port)



