# sanity-check.ps1
Write-Host "`n=== Sanity Check for Backend Deploy ===`n" -ForegroundColor Cyan

# Paths to check
$files = @(
    "backend/app/app.py",
    "backend/requirements.txt"
)

# Check if files exist locally
foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "Exists: $f" -ForegroundColor Green
    }
    else {
        Write-Host "MISSING: $f" -ForegroundColor Red
    }
}

# Confirm they are tracked by git
Write-Host "`nChecking if files are tracked by Git..." -ForegroundColor Yellow
$gitFiles = git ls-files backend

foreach ($f in $files) {
    if ($gitFiles -contains $f) {
        Write-Host "Tracked: $f" -ForegroundColor Green
    }
    else {
        Write-Host "NOT tracked: $f (use git add $f)" -ForegroundColor Red
    }
}

# Show backend tree for quick inspection
Write-Host "`nBackend folder contents:" -ForegroundColor Cyan
Get-ChildItem -Recurse backend | Select-Object FullName
