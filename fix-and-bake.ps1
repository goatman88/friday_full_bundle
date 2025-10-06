param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

function Say([string]$m,[string]$c="") { if($c){Write-Host $m -ForegroundColor $c}else{Write-Host $m} }
function Fail([string]$m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# Resolve path robustly even if invoked inline
if (-not $FrontendPath -or $FrontendPath -eq ".") {
  $scriptDir = if ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { (Get-Location).Path }
  $FrontendPath = Join-Path $scriptDir "frontend"
}

Say "=== Step 1: fix → bake → build → verify ===" "Cyan"
Say ("Backend : {0}" -f $Backend) "Yellow"
Say ("Frontend: {0}" -f $FrontendPath) "Yellow"

# 1) Fix main.js
$main = Join-Path $FrontendPath "src/main.js"
if (-not (Test-Path $main)) { Fail ("main.js not found at {0}" -f $main) }

# Read raw JS
$raw = Get-Content $main -Raw

# Remove backslashes that break Vite/Rollup (\api or \\api)
$raw = $raw -replace "(?i)fetch\(\s*['""]\\+/api","fetch('/api"      # rare safety
$raw = $raw -replace "(?i)fetch\(\s*['""]\\\\+/api","fetch('/api"    # typical on Windows newlines
$raw = $raw -replace "(?i)fetch\(\s*['""]\\api","fetch('/api"        # stray

# Prefer env if present; otherwise bake constant
if ($raw -notmatch "import\.meta\.env\.VITE_BACKEND_URL") {
  # inject a backend const at top if missing
  if ($raw -notmatch "const\s+backend\s*=") {
    $raw = "const backend = '$Backend';`r`n" + $raw
  } else {
    # normalize existing const backend
    $raw = $raw -replace "const\s+backend\s*=\s*.*?;","const backend = '$Backend';"
  }
  # convert relative fetch('/api/...') to absolute using baked const
  $raw = $raw -replace "(?i)fetch\(\s*['""]\/api","fetch(`${backend}/api"
} else {
  # env path: ensure fetch uses ${import.meta.env.VITE_BACKEND_URL}
  $raw = $raw -replace "const\s+backend\s*=\s*.*?;","const backend = import.meta.env.VITE_BACKEND_URL || '$Backend';"
  $raw = $raw -replace "(?i)fetch\(\s*['""]\/api","fetch(`${backend}/api"
}

# Guard against stray backticks that can trigger "Unterminated template"
# (This is a minimal no-op; keeps PowerShell from introducing lone backticks)
$raw = $raw -replace "(``)(?=[^`])","`$1"

Set-Content -Path $main -Value $raw -Encoding UTF8
Say "Patched src/main.js" "Green"

# 2) .env.local (Render Static Site reads env at build-time only if it's baked into code)
$envLocal = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envLocal
Say "Updated .env.local" "Green"

# 3) Build (clean-ish install to avoid lock/OS newline issues)
Push-Location $FrontendPath
try {
  if (Test-Path (Join-Path $FrontendPath 'node_modules')) { Remove-Item -Recurse -Force (Join-Path $FrontendPath 'node_modules') }
  if (Test-Path (Join-Path $FrontendPath 'dist'))         { Remove-Item -Recurse -Force (Join-Path $FrontendPath 'dist') }
  if (Test-Path (Join-Path $FrontendPath 'package-lock.json')) { Remove-Item -Recurse -Force (Join-Path $FrontendPath 'package-lock.json') }

  npm install | Out-Host
  Say "Building production bundle..." "DarkGray"
  npm run build | Out-Host
  Say "Local build completed." "Green"
}
catch { Fail ("Local build failed: {0}" -f $_.Exception.Message) }
finally { Pop-Location }

# 4) Verify bundle actually bakes the backend host
$assetsDir = Join-Path $FrontendPath "dist/assets"
if (!(Test-Path $assetsDir)) { Fail ("Build output not found at {0}" -f $assetsDir) }

$bundle = Get-ChildItem $assetsDir -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if (-not $bundle) { Fail "No built JS found under dist/assets" }

$content = Get-Content $bundle.FullName -Raw
$host = ([Uri]$Backend).Host

if ($content -match [regex]::Escape($host)) {
  Say ("[PASS] Baked OK: found host {0} in {1}" -f $host, $bundle.Name) "Green"
  Say "Done."
} else {
  Fail ("STILL NOT baked: host {0} not found in {1}. Search for 'fetch(' inside it to see what URL is used." -f $host, $bundle.Name)
}
