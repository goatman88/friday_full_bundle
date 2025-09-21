param (
    [string]$BackendUrl = "https://friday-099e.onrender.com"
)

Write-Host "Checking $BackendUrl/health ..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest "$BackendUrl/health"
    Write-Host "Health endpoint returned: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not reach backend. Logs needed." -ForegroundColor Red
}

Write-Host "Checking $BackendUrl/api/health ..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest "$BackendUrl/api/health"
    Write-Host "API Health endpoint returned: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not reach /api/health. Logs needed." -ForegroundColor Red
}

