param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Site
)

function Show([bool]$ok, [string]$msg) {
  if ($ok) { Write-Host "[PASS]" -ForegroundColor Green -NoNewline }
  else     { Write-Host "[FAIL]" -ForegroundColor Red   -NoNewline }
  Write-Host " $msg"
}

Write-Host "=== Friday Frontend Doctor (auto-check) ===" -ForegroundColor Cyan
Write-Host "Backend : $Backend"
Write-Host "Static  : $Site`n"

# 1) CORS preflight (OPTIONS)
try {
  $opt = Invoke-WebRequest -Method Options -Uri "$Backend/api/health" `
    -Headers @{ "Origin"=$Site; "Access-Control-Request-Method"="GET" } `
    -TimeoutSec 25 -ErrorAction Stop
  $acao = $opt.Headers['access-control-allow-origin']
  Show ($opt.StatusCode -eq 200) "CORS preflight OPTIONS /api/health (ACAO=$acao, status=$($opt.StatusCode))"
} catch { Show $false "CORS preflight failed: $($_.Exception.Message)" }

# 2) Real GET with Origin
try {
  $get = Invoke-WebRequest -Method GET -Uri "$Backend/api/health" `
    -Headers @{ "Origin"=$Site } `
    -TimeoutSec 25 -ErrorAction Stop
  $acao2 = $get.Headers['access-control-allow-origin']
  $ok = ($get.StatusCode -eq 200) -and ($get.Content -match '"status"\s*:\s*"ok"')
  Show $ok "GET $Backend/api/health (ACAO=$acao2, status=$($get.StatusCode))"
} catch { Show $false "GET with Origin failed: $($_.Exception.Message)" }

# 3) Find deployed bundle JS from index.html
$jsUrl = $null
try {
  $index = Invoke-WebRequest $Site -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
  $m = [regex]::Match($index.Content, '<script type="module" src="([^"]+\.js)"></script>')
  if (-not $m.Success) { throw "Could not find module JS in index.html" }
  $jsPath = $m.Groups[1].Value
  $jsUrl  = if ($jsPath -match '^https?://') { $jsPath } else {
    $left  = $Site.TrimEnd('/')
    $right = $jsPath.TrimStart('/')
    "$left/$right"
  }
  Show $true "Found bundle JS: $jsUrl"
} catch { Show $false "Parse index.html failed: $($_.Exception.Message)" }

# 4) Inspect bundle contents
$hasBackend = $false
$usesRelative = $false
if ($jsUrl) {
  try {
    $bundle = Invoke-WebRequest $jsUrl -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
    $backendHost  = ([Uri]$Backend).Host
    $hasBackend   = $bundle.Content -match [regex]::Escape($backendHost)
    $usesRelative = $bundle.Content -match "fetch\(['""]\/api"
    Show $hasBackend "Bundle references backend host ($backendHost) (baked absolute URL)"
    Show (-not $usesRelative) "Bundle does not use relative '/api/*' fetches"
  } catch { Show $false "Fetch bundle failed: $($_.Exception.Message)" }
}

# 5) Guidance
Write-Host ""
if (-not $hasBackend) {
  Write-Host "Result: Your deployed bundle does NOT include the backend host." -ForegroundColor Yellow
  Write-Host "Fix on Render (Static Site):" -ForegroundColor Yellow
  Write-Host "  1) Environment → keep ONLY this key:  VITE_BACKEND_URL = $Backend" -ForegroundColor Yellow
  Write-Host "  2) Manual Deploy → Clear build cache & Deploy (IMPORTANT)." -ForegroundColor Yellow
} elseif ($usesRelative) {
  Write-Host "Result: Bundle still contains relative '/api/*' calls." -ForegroundColor Yellow
  Write-Host "Ensure your code uses the baked env var or absolute URL (e.g. fetch(`$Backend/api/health`))." -ForegroundColor Yellow
} else {
  Write-Host "Result: Looks good. The bundle references the backend host and uses absolute URLs." -ForegroundColor Green
}
Write-Host "`n=== End ==="


