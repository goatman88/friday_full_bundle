param(
  [Parameter(Mandatory = $true)][string]$Backend,
  [string]$FrontendPath = ".\frontend"
)

function Say($t){ Write-Host $t -ForegroundColor Cyan }
function Ok($t){ Write-Host $t -ForegroundColor Green }
function Warn($t){ Write-Host $t -ForegroundColor Yellow }
function Fail($t){ Write-Host $t -ForegroundColor Red }

# Resolve paths safely (don't rely on $PSScriptRoot for pasted scripts)
try {
  $Front = Resolve-Path -LiteralPath $FrontendPath -ErrorAction Stop
} catch {
  Fail "Frontend folder not found at '$FrontendPath'. Run this from your project root (the folder that contains 'frontend')."
  exit 1
}

$envFile = Join-Path $Front ".env.local"
$vconf   = Join-Path $Front "vite.config.js"
$mainjs  = Join-Path $Front "src\main.js"

Say "=== Friday Auto-Patch ==="
Say "Using backend: $Backend"
Say "Frontend at:  $($Front.Path)"

# 1) Write .env.local for local dev
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 -NoNewline $envFile
Ok "Wrote $envFile"

# 2) Ensure dev proxy in vite.config.js points to backend (if the file exists)
if (Test-Path $vconf) {
  $v = Get-Content -Raw $vconf
  # naive replace of any 'target:' line inside a proxy block
  $v = $v -replace "target:\s*['""]https?:\/\/[^'""]+['""]", "target: '$Backend'"
  Set-Content -Encoding UTF8 $vconf $v
  Ok "Patched dev proxy in vite.config.js (for npm run dev)"
} else {
  Warn "vite.config.js not found (that's ok if you don't need the dev proxy)."
}

# 3) Patch src/main.js fetches to bake absolute URLs at build time
if (-not (Test-Path $mainjs)) {
  Fail "Expected file not found: $mainjs"
  exit 1
}

$js = Get-Content -Raw $mainjs

# Replace common relative calls: '/api/...'
$js = $js -replace "fetch\(\s*(['""])/api/", "fetch(`${import.meta.env.VITE_BACKEND_URL}/api/"
# Also handle template literals like fetch(`/api/...`)
$js = $js -replace "fetch\(\s*`/api/", "fetch(`${import.meta.env.VITE_BACKEND_URL}/api/"

Set-Content -Encoding UTF8 $mainjs $js
Ok "Patched $mainjs to use import.meta.env.VITE_BACKEND_URL"

# 4) Build frontend and verify the bundle contains the backend host
Push-Location $Front
try {
  Say "Running npm install…"
  npm i | Out-Host
  Ok "npm install ok"

  Say "Building production bundle…"
  npm run build | Out-Host
  Ok "vite build ok"
} catch {
  Pop-Location
  Fail "Build failed: $($_.Exception.Message)"
  exit 1
}
Pop-Location

# 5) Verify the baked URL appears inside built JS
$dist = Join-Path $Front "dist\assets"
if (-not (Test-Path $dist)) {
  Fail "Build output not found at $dist"
  exit 1
}
$jsFiles = Get-ChildItem $dist -Filter *.js -Recurse
$found = $false
foreach ($f in $jsFiles) {
  $c = Get-Content -Raw $f.FullName
  if ($c -match [regex]::Escape($Backend)) {
    $found = $true
    Ok "PASS: backend host found in bundle ⇒ $($f.Name)"
    break
  }
}

if (-not $found) {
  Fail "FAIL: backend host NOT found in built JS. Ensure code uses import.meta.env.VITE_BACKEND_URL and re-run."
  exit 1
}

Ok "Build complete. Backend baked in: $Backend"
Warn "Remember (Render Static Site): set Environment key VITE_BACKEND_URL=$Backend, then 'Manual Deploy' → 'Clear build cache & deploy'."



