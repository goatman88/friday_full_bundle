# Always jump to your repo root (adjust if your path differs)
cd "C:\Users\mtw27\friday-frontend"
Write-Host "Now in repo root: $((Get-Location).Path)" -ForegroundColor Green
git rev-parse --abbrev-ref HEAD

