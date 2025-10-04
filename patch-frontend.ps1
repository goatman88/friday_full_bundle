param(
  [Parameter(Mandatory = $true)][string]$Backend
)

$ErrorActionPreference = 'Stop'

function Say($msg) { Write-Host $msg -ForegroundColor Cyan }
function Done($msg) { Write-Host $msg -ForegroundColor Green }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

# --- Paths ---
$root      = $PSScriptRoot
$fe        = Join-Path $root 'frontend'
$envFile   = Join-Path $fe '.env.local'
$viteFile  = Join-Path $fe 'vite.config.js'
$distDir   = Join-Path $fe 'dist'

if (-not (Test-Path $fe)) { Fail "frontend/ not found at $fe"; exit 1 }

Say "Patching frontend to bake backend URL:`n  $Backend"

# --- 1) Ensure .env.local contains VITE_BACKEND_URL (used by dev too) ---
"VITE_BACKEND_URL=$Backend`n" | Out-File -Encoding UTF8 $envFile
Done "Updated $envFile"

# --- 2) Ensure vite dev proxy points at your backend (for local npm run dev) ---
if (Test-Path $viteFile) {
  $vite = Get-Content $viteFile -Raw
  if ($vite -notmatch "server\s*:\s*{") {
    # add a minimal dev server with proxy
    $vite = $vite -replace 'export default \({', "export default ({`n  server: { proxy: { '/api': { target: '$Backend', changeOrigin: true, secure: true } } },"
  } else {
    # replace any existing '/api' proxy target with your backend
    $vite = $vite -replace "(?ms)'/api'\s*:\s*\{[^}]*target:\s*'[^']+'", "'/api': { target: '$Backend'"
  }
  Set-Content -Encoding UTF8 $viteFile $vite
  Done "Patched vite.config.js"
} else {
  Write-Host "vite.config.js not found (skipping dev proxy)" -ForegroundColor Yellow
}

# --- 3) Clean previous build output so cache can’t bite us locally ---
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }

# --- 4) Install & build production bundle ---
Push-Location $fe
try {
  Say "Installing npm packages…"
  if (Test-Path "package-lock.json") { npm ci | Out-Host } else { npm i | Out-Host }
  Done "npm install ok"

  Say "Building production bundle…"
  npm run build | Out-Host
  Done "vite build ok"
}
catch {
  Pop-Location
  Fail $_.Exception.Message
  exit 1
}
Pop-Location

# --- 5) Verify the bundle actually contains the backend host ---
$jsFiles = Get-ChildItem -Path (Join-Path $distDir 'assets') -Filter *.js -Recurse -ErrorAction SilentlyContinue
if (-not $jsFiles) { Fail "No JS assets found under $distDir"; exit 1 }

$host = ([uri]$Backend).Host
$hasBackend = $false
foreach ($f in $jsFiles) {
  $c = Get-Content $f.FullName -Raw
  if ($c -match [regex]::Escape($host)) { $hasBackend = $true; break }
}

if ($hasBackend) {
  Done "Build contains backend host '$host'. ✅"
  Write-Host ""
  Write-Host "Next steps:" -ForegroundColor DarkGray
  Write-Host "  1) Commit the patch if needed:  git add frontend/.env.local frontend/vite.config.js; git commit -m `"Frontend: bake backend into build`""
  Write-Host "  2) Push to GitHub:              git push"
  Write-Host "  3) On Render (Static Site):     Environment = keep ONLY:  VITE_BACKEND_URL=$Backend"
  Write-Host "  4) On Render (Static Site):     Manual Deploy → Clear build cache & Deploy"
} else {
  Fail "Bundle does NOT include backend host '$host'."
  Write-Host "If this is a Render deploy: set VITE_BACKEND_URL in the Static Site → Environment, then Manual Deploy → Clear build cache & Deploy." -ForegroundColor Yellow
  exit 2
}


