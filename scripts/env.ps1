# scripts/env.ps1
Param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$FrontendBase = "http://localhost:5173"
)

Write-Host "Setting dev environment variables..." -ForegroundColor Cyan

$env:VITE_API_BASE      = $ApiBase
$env:VITE_BACKEND_BASE  = $ApiBase
$env:VITE_SESSION_ID    = "local-dev"

# Optional CORS loosen for backend
$env:CORS_ALLOW_ORIGINS = "$FrontendBase,$ApiBase,*"

Write-Host "`nCurrent ENV:" -ForegroundColor Green
"VITE_API_BASE=$env:VITE_API_BASE"
"VITE_BACKEND_BASE=$env:VITE_BACKEND_BASE"
"VITE_SESSION_ID=$env:VITE_SESSION_ID"
"CORS_ALLOW_ORIGINS=$env:CORS_ALLOW_ORIGINS" | ForEach-Object { Write-Host $_ }

