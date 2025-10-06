param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

function Say([string]$m,[string]$c=""){ if($c){Write-Host $m -ForegroundColor $c}else{Write-Host $m} }
function Fail([string]$m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# Resolve to script folder if run inline
if (-not $FrontendPath -or $FrontendPath -eq ".") {
  $scriptDir = if ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { Get-Location }.Path
  $FrontendPath = Join-Path $scriptDir "frontend"
}

Say "=== Step 1: fix → bake → build → verify ===" "Cyan"
Say ("Backend : {0}" -f $Backend) "Yellow"
Say ("Frontend: {0}" -f $FrontendPath) "Yellow"

# 1) Fix main.js
$main = Join-Path $FrontendPath "src/main.js"
if (-not (Test-Path $main)) { Fail ("main.js not found at {0}" -f $main) }

# Read and normalize content
$raw = Get-Content $main -Raw

# Remove any bad backslashes that break Vite/Rollup
$raw = $raw -replace "(?i)fetch\(\s*['""]\\\\api","fetch('/api"       # rare safety
$raw = $raw -replace "(?i)fetch\(\s*['""]\\\/api","fetch('/api"       # rare safety
$raw = $raw -replace "(?i)fetch\(\s*['""]/api","fetch('/api"          # typical

# Prefer env if present; else bake a `backend` const
if ($raw -notmatch 'import\.meta\.env\.VITE_BACKEND_URL') {
  if ($raw -notmatch 'const\s+backend\s*='){
    $raw = "const backend = '$Backend';`r`n" + $raw
  } else {
    $raw = $raw -replace "const\s+backend\s*=\s*.*?;","const backend = '$Backend';"
  }
  # Convert relative calls to absolute using baked const
  $raw = $raw -replace "fetch\(\s*['""]/api","fetch(`${backend}/api"
} else {
  # Ensure all fetches use the env var
  $raw = $raw -replace "const\s+backend\s*=.*?;","const backend = import.meta.env.VITE_BACKEND_URL || '$Backend';"
  $raw = $raw -replace "fetch\(\s*['""]/api","fetch(`${backend}/api"
}

# Guard against stray backticks (template parsing)
$raw = $raw -replace "(``)(?=[^`])","`$1"   # keep any accidental naked backticks paired

Set-Content -Path $main -Value $raw -Encoding UTF8
Say "Patched src/main.js" "Green"

# 2) .env.local for Render (static) build-time reads
$envLocal = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envLocal
Say "Updated .env.local" "Green"

# 3) Build (clean-ish install to avoid lock/CRLF issues)
Push-Location $FrontendPath
try{
  if (Test-Path (Join-Path $FrontendPath 'node_modules')){ Remove-Item -Recurse -Force (Join-Path $FrontendPath 'node_modules') }
  if (Test-Path (Join-Path $FrontendPath 'dist'))       { Remove-Item -Recurse -Force (Join-Path $FrontendPath 'dist') }
  if (Test-Path (Join-Path $FrontendPath 'package-lock.json')) { Remove-Item -Force (Join-Path $FrontendPath 'package-lock.json') }

  npm install  | Out-Host
  Say "Building production bundle..." "DarkGray"
  npm run build | Out-Host
  Say "Local build completed." "Green"
}
catch { Fail ("Local build failed: {0}" -f $_.Exception.Message) }
finally { Pop-Location }

# 4) Verify bundle actually bakes the backend host
$assetsDir = Join-Path $FrontendPath "dist/assets"
if (-not (Test-Path $assetsDir)) { Fail ("Build output not found at {0}" -f $assetsDir) }

$bundle = Get-ChildItem $assetsDir -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if (-not $bundle) { Fail "No built JS found under dist/assets" }

$content = Get-Content $bundle.FullName -Raw
$backendHost = ([Uri]$Backend).Host
if ($content -match ([regex]::Escape($backendHost))) {
  Say ("[PASS] Baked OK: found host {0} in {1}" -f $backendHost, $bundle.Name) "Green"
} else {
  Fail ("STILL NOT baked: host {0} not found in {1}. Search for `fetch(` inside it to see what URL is used." -f $backendHost, $bundle.Name)
}
