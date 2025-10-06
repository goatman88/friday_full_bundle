param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath
)

function Say($m,[string]$c=""){ if($c){Write-Host $m -ForegroundColor $c}else{Write-Host $m} }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# Resolve frontend path reliably whether script is run as a file or pasted
if (-not $FrontendPath -or $FrontendPath.Trim() -eq "") {
  $scriptDir = if ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { (Get-Location).Path }
  $FrontendPath = Join-Path $scriptDir 'frontend'
}

Say "== Step 1 fixer: remove bad backslashes, switch to absolute fetch(), build, and verify ==" "Cyan"
Say ("Backend : {0}" -f $Backend) "Yellow"
Say ("Frontend: {0}" -f $FrontendPath)

# --- 0) sanity
if (-not (Test-Path $FrontendPath)) { Fail ("Frontend folder not found at {0}" -f $FrontendPath) }

# --- 1) fix main.js text
$main = Join-Path $FrontendPath 'src\main.js'
if (-not (Test-Path $main)) { Fail ("main.js not found at {0}" -f $main) }

# Read as text, fix the two common problems:
#  - backslashes in fetch path
#  - ensure absolute backend URL is used in fetch
$raw = Get-Content $main -Raw

# Remove double-backslashes like \\api or \\/api
$raw = $raw -replace '(?i)fetch\(\s*\\\\+/api','fetch("/api' # safety
$raw = $raw -replace '(?i)fetch\(\s*\\\\api','fetch("/api'  # typical case
$raw = $raw -replace '(?i)fetch\(\s*\\api','fetch("/api'    # leftover

# If code uses env var already, prefer it; else bake absolute
if ($raw -notmatch 'import\.meta\.env\.VITE_BACKEND_URL') {
  # insert a backend const if missing
  if ($raw -notmatch 'const\s+backend\s*=') {
    $raw = "const backend = '$Backend';`r`n" + $raw
  } else {
    # replace any placeholder backend assignment
    $raw = $raw -replace "const\s+backend\s*=.*?;","const backend = '$Backend';"
  }
  # switch fetch("/api/..") → fetch(`${backend}/api/..`)
  $raw = $raw -replace 'fetch\("?/api','fetch(`${backend}/api'
} else {
  # keep env, but ensure fetch uses the env value
  $raw = $raw -replace 'fetch\("?/api','fetch(`${import.meta.env.VITE_BACKEND_URL}/api'
}

# Write back as UTF8 (no BOM)
Set-Content -Path $main -Value $raw -Encoding UTF8
Say "Patched src\main.js" "Green"

# --- 2) (optional) write .env.local so Vite can inject it if used
$envLocal = Join-Path $FrontendPath '.env.local'
"VITE_BACKEND_URL=$Backend" | Out-File -FilePath $envLocal -Encoding UTF8
Say "Updated .env.local" "Green"

# --- 3) build
Push-Location $FrontendPath
try {
  Say "Running npm install..." "DarkGray"
  npm install | Out-Host
  Say "Building production bundle..." "DarkGray"
  npm run build | Out-Host
  Say "Local build completed." "Green"
}
catch {
  Fail ("Local build failed: {0}" -f $_.Exception.Message)
}
finally { Pop-Location }

# --- 4) verify bundle has backend host
$assets = Join-Path $FrontendPath 'dist\assets'
if (!(Test-Path $assets)) { Fail ("Build output not found at {0}" -f $assets) }
$bundle = Get-ChildItem $assets -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if (-not $bundle) { Fail "No built JS found under dist/assets" }
$content = Get-Content $bundle.FullName -Raw

$host = ([Uri]$Backend).Host
if ($content -match [regex]::Escape($host)) {
  Say ("Baked OK: found backend host '{0}' in {1}" -f $host, $bundle.Name) "Yellow"
} else {
  Fail ("STILL NOT baked: backend host '{0}' not found in {1}. Open this file and search for 'fetch(' to see what URL is used." -f $host, $bundle.Name)
}

Say "Done."
