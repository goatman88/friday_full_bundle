$roots = @(
  "C:\Users\mtw27\friday-frontend\friday-frontend",
  "$HOME\friday-frontend\friday-frontend"
)
$found = $null
foreach ($r in $roots) { if (Test-Path $r) { $found = $r; break } }
if ($found) {
  Set-Location $found
  Write-Host ("Repo root: {0}" -f (Get-Location).Path) -ForegroundColor Green
  git rev-parse --abbrev-ref HEAD | % { Write-Host ("Branch: " + $_) -ForegroundColor Yellow }
} else {
  Write-Host "Could not locate repo root. cd there manually." -ForegroundColor Red
}


