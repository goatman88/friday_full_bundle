param(
  [Parameter(Mandatory=$true)][string]$Backend,              # e.g. https://friday-backend-ksep.onrender.com
  [string]$FrontendPath = "$PSScriptRoot/frontend"          # leave default
)

function Say([string]$msg,[string]$color="") { if ($color) { Write-Host $msg -ForegroundColor $color } else { Write-Host $msg } }
function Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Say "=== Step 1 fixer: remove bad backslashes, switch to absolute fetch(), build, and verify ===" "Cyan"
Say "Backend: $Backend" "Yellow"
Say "Frontend: $FrontendPath"

if (!(Test-Path $FrontendPath)) { Fail "Frontend folder not found at $FrontendPath"; exit 1 }

$src = Join-Path $FrontendPath "src/main.js"
if (!(Test-Path $src)) { Fail "main.js not found at $src"; exit 1 }

# 1) Fix backslashes and relative /api/* calls
Say "Patching $src ..." "Yellow"
$content = Get-Content $src -Raw

# a) collapse backslashes:  \\api → /api
$content = $content -replace "\\\\+api","/api"

# b) replace fetch('/api...') or fetch("/api...") with absolute backend URL
#    we keep the rest of the path after /api
$backendEsc = [Regex]::Escape($Backend.TrimEnd('/'))
$content = [Regex]::Replace(
  $content,
  "fetch\(\s*(['""])\s*/api(/[^'""]*)\1\s*\)",
  "fetch(`"$backendEsc/api$2`")"
)

# c) if code uses template literal fetch(`/api/...`) switch to absolute
$content = [Regex]::Replace(
  $content,
  "fetch\(\s*`/api(/[^`]*)`\s*\)",
  "fetch(`"$backendEsc/api$1`")"
)

Set-Content -Encoding UTF8 $src $content
Say "Patched main.js" "Green"

# 2) (Optional) write .env.local for local dev parity
$envLocal = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envLocal
Say "Wrote .env.local (for local dev): VITE_BACKEND_URL" "Green"

# 3) Build
Push-Location $FrontendPath
try {
  Say "Running npm install..." "DarkGray"
  npm install | Out-Host
  Say "Building production bundle..." "DarkGray"
  npm run build | Out-Host
  Say "Local build completed." "Green"
} catch {
  Fail ("Local build failed: {0}" -f $_.Exception.Message)
  Pop-Location
  exit 1
}
Pop-Location

# 4) Sanity: verify the built JS includes the backend host
$assets = Join-Path $FrontendPath "dist/assets"
if (!(Test-Path $assets)) { Fail "Build output not found at $assets"; exit 1 }

$bundle = Get-ChildItem $assets -Filter *.js | Select-Object -First 1
if (-not $bundle) { Fail "Could not find a built *.js in dist/assets"; exit 1 }

$host = ([Uri]$Backend).Host
$bundleText = Get-Content $bundle.FullName -Raw
if ($bundleText -match [Regex]::Escape($host)) {
  Say "PASS: baked backend host '$host' is present in $($bundle.Name)" "Green"
  exit 0
} else {
  Fail "Still NOT baked: could not find backend host '$host' in $($bundle.Name)."
  Say "Open $($bundle.Name) and search for 'fetch(' to see what URL remains." "Yellow"
  exit 2
}
