param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

function Say($m){ Write-Host $m -ForegroundColor Cyan }
function Done($m){ Write-Host $m -ForegroundColor Green }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

Write-Host "🛠  Patching frontend to bake backend URL: $Backend" -ForegroundColor Yellow

if (!(Test-Path $FrontendPath)) { Fail "Frontend folder not found at $FrontendPath" }

# 1) .env.local for dev & for build-time variable
$envFile = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envFile
Done "Wrote .env.local"

# 2) Ensure vite proxy points at backend for dev
$vite = Join-Path $FrontendPath "vite.config.js"
if (!(Test-Path $vite)) { Fail "vite.config.js not found" }
# (File we ship already reads VITE_BACKEND_URL, so nothing else to do)
Done "vite.config.js ok"

# 3) Build
Push-Location $FrontendPath
try{
  Say "Installing npm deps…"
  npm i | Out-Host
  Done "npm install ok"

  Say "Building production bundle…"
  npm run build | Out-Host
  Done "vite build ok"
}
catch{
  Pop-Location
  Fail $_.Exception.Message
}
Pop-Location

# 4) Verify bundle contains the backend host
$dist = Join-Path $FrontendPath "dist"
if (!(Test-Path $dist)) { Fail "Build output not found at $dist" }

$indexPath = Join-Path $dist "index.html"
if (!(Test-Path $indexPath)) { Fail "dist/index.html not found" }

$idx = Get-Content $indexPath -Raw
$jsPath = [regex]::Match($idx,'src="([^"]+\.js)"').Groups[1].Value
if (-not $jsPath) { Fail "Could not find built JS in index.html" }

$jsUrl = if ($jsPath -match '^https?://') { $jsPath } else {
  $left  = $dist.TrimEnd('\','/')
  $right = $jsPath.TrimStart('\','/')
  Join-Path $left $right
}

$js = if (Test-Path $jsUrl) { Get-Content $jsUrl -Raw } else { (Invoke-WebRequest $jsUrl -UseBasicParsing).Content }
$host = ([uri]$Backend).Host
$hasBackend = $js -match [regex]::Escape($host)
if ($hasBackend) { Done "✅ Backend host is baked into the bundle ($host)" }
else             { Fail "Bundle does NOT contain backend host ($host). On Render Static Site: keep ONLY env key VITE_BACKEND_URL=$Backend, then Clear build cache & Deploy." }


