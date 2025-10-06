param(
  [Parameter(Mandatory=$true)][string]$Backend,   # e.g. https://friday-backend-ksep.onrender.com
  [Parameter(Mandatory=$true)][string]$Site,      # e.g. https://friday-full-bundle.onrender.com
  [switch]$CheckLocal,                            # also check local source file issues
  [switch]$AutoFix                                # attempt simple fixes in repo
)

function Say([string]$msg,[ConsoleColor]$c=[ConsoleColor]::Gray){ $fc=$Host.UI.RawUI.ForegroundColor; $Host.UI.RawUI.ForegroundColor=$c; Write-Host $msg; $Host.UI.RawUI.ForegroundColor=$fc }
function Pass([string]$m){ Say "[PASS] $m" "Green" }
function Fail([string]$m){ Say "[FAIL] $m" "Red" }
function Info([string]$m){ Say $m "Cyan" }
function Warn([string]$m){ Say $m "Yellow" }

function TryReq($scriptBlock){
  try { & $scriptBlock }
  catch { $_ }
}

Info "=== Friday Frontend Doctor (auto-check) ==="
Say  ("Backend : {0}" -f $Backend) "DarkGray"
Say  ("Static  : {0}" -f $Site) "DarkGray"
""

# ---- 1) CORS preflight (OPTIONS) with proper Origin ----
$opt = TryReq { Invoke-WebRequest -Method Options -Uri "$Backend/api/health" -TimeoutSec 25 -Headers @{ "Origin"=$Site; "Access-Control-Request-Method"="GET" } -ErrorAction Stop }
if ($opt -is [System.Management.Automation.ErrorRecord]) {
  Fail ("CORS preflight OPTIONS failed: {0}" -f $opt.Exception.Message)
} else {
  $acao = $opt.Headers['access-control-allow-origin']
  if ($opt.StatusCode -eq 200 -and $acao -match $Site) {
    Pass ("CORS preflight ok (ACAO={0}, status={1})" -f $acao, $opt.StatusCode)
  } else {
    Fail ("CORS preflight: status={0}, ACAO={1}" -f $opt.StatusCode, $acao)
  }
}

# ---- 2) Actual GET with Origin ----
$get = TryReq { Invoke-WebRequest -Method GET -Uri "$Backend/api/health" -TimeoutSec 25 -Headers @{ "Origin"=$Site } -ErrorAction Stop }
if ($get -is [System.Management.Automation.ErrorRecord]) {
  Fail ("GET $Backend/api/health failed: {0}" -f $get.Exception.Message)
} else {
  $acao2 = $get.Headers['access-control-allow-origin']
  $ok2   = ($get.StatusCode -eq 200) -and ($acao2 -match $Site) -and ($get.Content -match '"status"\s*:\s*"ok"')
  if ($ok2) { Pass ("GET ok (status={0}, ACAO={1})" -f $get.StatusCode, $acao2) } else { Fail ("GET status={0}, ACAO={1}, body={2}" -f $get.StatusCode,$acao2,$get.Content.Trim()) }
}

# ---- 3) Locate deployed JS bundle from index.html ----
$jsUrl = $null
$index = TryReq { Invoke-WebRequest $Site -UseBasicParsing -TimeoutSec 25 -ErrorAction Stop }
if ($index -is [System.Management.Automation.ErrorRecord]) {
  Fail ("Fetch index.html failed: {0}" -f $index.Exception.Message)
} else {
  # Try link parsing first
  $jsPath = ($index.Links | Where-Object { $_.href -match '\.js$' } | Select-Object -First 1).href
  if (-not $jsPath) {
    # Fallback regex on content
    $m = [regex]::Match($index.Content, 'src\s*=\s*"(\/?assets\/[^\"]+\.js)"',[System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) { $jsPath = $m.Groups[1].Value }
  }
  if ($jsPath) {
    if ($jsPath -match '^https?://') { $jsUrl = $jsPath }
    else {
      $left  = $Site.TrimEnd('/')
      $right = $jsPath.TrimStart('/')
      $jsUrl = "$left/$right"
    }
    Pass ("Found bundle JS: $jsUrl")
  } else {
    Fail "Could not locate bundle .js in index.html"
  }
}

# ---- 4) Inspect bundle for baked backend + stray relative '/api/' ----
$hasBackend = $false
$usesRelative = $false
if ($jsUrl) {
  $bundle = TryReq { Invoke-WebRequest $jsUrl -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop }
  if ($bundle -is [System.Management.Automation.ErrorRecord]) {
    Fail ("Fetch bundle failed: {0}" -f $bundle.Exception.Message)
  } else {
    $backendHost = ([Uri]$Backend).Host
    $escBackend  = [regex]::Escape($backendHost)
    $hasBackend  = $bundle.Content -match $escBackend
    $usesRelative = $bundle.Content -match 'fetch\(\s*["' + "'" + ']/api/'
    if ($hasBackend)   { Pass  "Bundle contains backend host (baked absolute URL)" } else { Fail "Bundle does NOT include backend host" }
    if ($usesRelative) { Warn  "Bundle still contains relative '/api/*' fetches (will hit wrong origin)" } else { Pass "No relative '/api/*' fetches found" }
    $first = ([regex]::Match($bundle.Content,'https?://[^"''\s]+/api/health')).Value
    if ($first) { Say ("First absolute /api/health in bundle: {0}" -f $first) "DarkGray" }
  }
}

# ---- 5) Optional: local source checks/fixes ----
$repoRoot = $PSScriptRoot
$front    = Join-Path $repoRoot 'frontend'
$srcMain  = Join-Path $front 'src\main.js'
$envFile  = Join-Path $front '.env.local'
$viteCfg  = Join-Path $repoRoot 'frontend\vite.config.js'

if ($CheckLocal) {
  if (Test-Path $srcMain) {
    $main = Get-Content $srcMain -Raw
    if ($main -match 'fetch\(\s*\\\\/api/') {
      Fail "main.js has backslashes in fetch('\\\/api/...') → causes 'Expected unicode escape'."
      Say  "Fix: use fetch('/api/...') for dev, or better: fetch(`${import.meta.env.VITE_BACKEND_URL}/api/...`)." "Yellow"
    } elseif ($main -match 'fetch\(\s*["' + "'" + ']/api/') {
      Warn "main.js uses relative '/api/*' (ok for dev proxy, **not** for static prod)."
    } else {
      Pass "main.js does not use bare relative '/api/*'."
    }
  } else {
    Warn "front/src/main.js not found, skipping local source checks."
  }
}

if ($AutoFix) {
  if (!(Test-Path $front)) { Fail "Frontend folder not found at $front"; exit 1 }
  # 5a) Ensure .env.local with absolute backend
  "VITE_BACKEND_URL=$Backend`n" | Out-File -Encoding UTF8 $envFile
  Pass "Wrote $($envFile | Split-Path -Leaf)"

  # 5b) Add a dev proxy (non-breaking)
  if (Test-Path $viteCfg) {
    $v = Get-Content $viteCfg -Raw
    if ($v -notmatch 'server:\s*\{') {
      $v = $v -replace 'defineConfig\(\(\)\s*=>\s*\(\{','defineConfig(() => ({ server: { proxy: { "/api": { target: "'+$Backend+'", changeOrigin: true, secure: true } } },'
    } else {
      # naive add/replace proxy block
      $v = $v -replace 'server\s*:\s*\{[^\}]*\}','server: { proxy: { "/api": { target: "'+$Backend+'", changeOrigin: true, secure: true } } }'
    }
    Set-Content -Encoding UTF8 $viteCfg $v
    Pass "Patched vite.config.js dev proxy"
  } else {
    Warn "vite.config.js not found; skipped proxy patch."
  }

  # 5c) Convert obvious relative fetches to baked env var
  if (Test-Path $srcMain) {
    $m = Get-Content $srcMain -Raw
    $m = $m -replace "fetch\(\s*['""]\/api\/","fetch(`${import.meta.env.VITE_BACKEND_URL}/api/"
    Set-Content -Encoding UTF8 $srcMain $m
    Pass "Rewrote simple relative fetch() calls to use VITE_BACKEND_URL"
  }

  # 5d) Build (to verify we can embed the backend)
  Push-Location $front
  try {
    Say "npm i (skip if already installed)…" "DarkGray"; npm i | Out-Null
    Say "vite build…" "DarkGray"; npm run build | Out-Null
    Pass "Local build completed. You can commit & push:"
    Say  "  git add frontend/src/main.js frontend/.env.local frontend/vite.config.js" "DarkGray"
    Say  "  git commit -m 'Frontend: bake backend & remove relative /api/*'" "DarkGray"
    Say  "  git push" "DarkGray"
    Say  "Then in Render (Static Site): Environment → keep ONLY:  VITE_BACKEND_URL = $Backend" "Yellow"
    Say  "Click **Manual Deploy** → **Clear build cache & Deploy**." "Yellow"
  } catch {
    Fail ("Local build failed: {0}" -f $_.Exception.Message)
  } finally { Pop-Location }
}

# ---- 6) Final guidance ----
Write-Host ""
Say "--- Final guidance ---" "Cyan"
if (-not $hasBackend) {
  Say "Result: Your deployed bundle does NOT include the backend host." "Yellow"
  Say "Fix on Render (Static Site): keep ONLY this key:  VITE_BACKEND_URL = $Backend" "Yellow"
  Say "Then Manual Deploy → Clear build cache & Deploy (IMPORTANT)." "Yellow"
} elseif ($usesRelative) {
  Say "Result: Bundle still contains relative '/api/*' calls." "Yellow"
  Say "Ensure your code uses the baked env var, e.g. fetch(`${import.meta.env.VITE_BACKEND_URL}/api/health`)." "Green"
} else {
  Say "Result: Looks good. The bundle references the backend host and uses absolute URLs." "Green"
}
Say "=== End ===" "Cyan"
