# Local dev env
$env:VITE_API_BASE = "http://localhost:8000"
$env:VITE_BACKEND_BASE = "http://localhost:8000"
$env:VITE_SESSION_ID = "local-dev"
Write-Host "Environment set:"
Write-Host "Backend : $env:VITE_BACKEND_BASE"
Write-Host "Frontend: http://localhost:5173"


