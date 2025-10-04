param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

Write-Host "== Friday Frontend Auto Patch ==" -ForegroundColor Cyan
Write-Host "Using backend: $Backend" -ForegroundColor Yellow

# 0) sanity
if (!(Test-Path $FrontendPath)) {
  Write-Host "✗ Frontend folder not found at $FrontendPath" -ForegroundColor Red
  exit 1
}

$src  = Join-Path $FrontendPath "src/main.js"
$vite = Join-Path $FrontendPath "vite.config.js"
$envL = Join-Path $FrontendPath ".env.local"

if (!(Test-Path $src))  { throw "src/main.js not found at $src" }
if (!(Test-Path $vite)) { throw "vite.config.js not found at $vite" }

# 1) bake absolute backend URL into main.js (replace any relative /api/* fetches)
$js = Get-Content $src -Raw

# repair accidental double backslashes if present
$js = $js -replace "fetch\(\s*\\\\\s*api","fetch('/api'"

# replace relative fetch('/api/...') or fetch("/api/...")
$js = $js -replace "fetch\(\s*(['`""])\s*/api","fetch('$Backend/api"

Set-Content -Encoding UTF8 $src $js
Write-Host "✓ main.js updated to use absolute $Backend/api/*" -ForegroundColor Green

# 2) ensure Vite dev proxy points to same backend (dev only)
$v = Get-Content $vite -Raw
if ($v -match "server\s*:\s*\{") {
  # replace existing '/api' proxy block
  $v = $v -replace "'/api'\s*:\s*\{[^\}]*\}",
    "'/api': { target: '$Backend', changeOrigin: $true, secure: $true }"
} else {
  # inject a server proxy section
  $v = $v -replace "defineConfig\(\{",
    ("defineConfig({`n  server: { proxy: { '/api': { target: '" + $Backend + "', changeOrigin: true, secure: true } } },")
}
Set-Content -Encoding UTF8 $vite $v
Write-Host "✓ vite.config.js dev proxy set to $Backend" -ForegroundColor Green

# 3) local env for dev (Render will ignore .env.local)
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envL
Write-Host "✓ .env.local written (dev only)" -ForegroundColor Green

# 4) build
Push-Location $FrontendPath
Write-Host "→ npm ci" -ForegroundColor DarkGray
npm ci
Write-Host "→ npm run build" -ForegroundColor DarkGray
npm run build
Pop-Location

Write-Host "✓ Build complete. Bundle now references $Backend" -ForegroundColor Green
Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  1) Commit & push:  git add frontend/src/main.js frontend/vite.config.js ; git commit -m ""Frontend: bake backend into build"" ; git push" -ForegroundColor Gray
Write-Host "  2) On Render (Static Site): Manual Deploy → Clear build cache & Deploy" -ForegroundColor Gray





