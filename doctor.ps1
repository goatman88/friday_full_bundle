param(
  [Parameter(Mandatory=$true)][string]$Backend,   # e.g. https://friday-backend-ksep.onrender.com
  [Parameter(Mandatory=$true)][string]$Site       # e.g. https://friday-full-bundle.onrender.com
)

function Show($ok, $msg) {
  if ($ok) { Write-Host "[PASS]" -ForegroundColor Green -NoNewline }
  else      { Write-Host "[FAIL]" -ForegroundColor Red -NoNewline }
  Write-Host " $msg"
}

# ---------- 0) normalize ----------
$Backend = $Backend.TrimEnd('/')
$Site    = $Site.TrimEnd('/')

Write-Host "Backend: $Backend"
Write-Host "Site:    $Site"
Write-Host ""

# ---------- 1) CORS preflight like a browser ----------
try {
  $opt = Invoke-WebRequest `
    -Method Options `
    -Uri "$Backend/api/health" `
    -Headers @{ "Origin"=$Site; "Access-Control-Request-Method"="GET" } `
    -TimeoutSec 25 -ErrorAction Stop

  $acao = $opt.Headers['access-control-allow-origin']
  $ok = ($opt.StatusCode -eq 200) -and $acao -and ($acao -eq $Site -or $acao -eq "*")
  Show $ok "CORS preflight OPTIONS /api/health -> $($opt.StatusCode)  ACAO='$acao'"
}
catch {
  Show $false "CORS preflight OPTIONS failed: $($_.Exception.Message)"
}

# ---------- 2) Actual GET with Origin header ----------
try {
  $get = Invoke-WebRequest `
    -Method GET `
    -Uri "$Backend/api/health" `
    -Headers @{ "Origin"=$Site } `
    -TimeoutSec 25 -ErrorAction Stop

  $acao2 = $get.Headers['access-control-allow-origin']
  $body  = $get.Content.Trim()
  $ok = ($get.StatusCode -eq 200) -and $body -match '"status"\s*:\s*"ok"' -and ($acao2 -eq $Site -or $acao2 -eq "*")
  Show $ok "GET /api/health -> $($get.StatusCode)  ACAO='$acao2'  body=$body"
}
catch {
  Show $false "GET /api/health failed: $($_.Exception.Message)"
}

# ---------- 3) Fetch index.html, find the JS bundle URL ----------
try {
  $index = Invoke-WebRequest "$Site" -UseBasicParsing -TimeoutSec 25 -ErrorAction Stop
  # find first <script type="module" src="...*.js">
  $m = [regex]::Match($index.Content, '<script[^>]*type="module"[^>]*src="([^"]+\.js)"', 'IgnoreCase')
  if (-not $m.Success) { throw "Could not locate the JS bundle tag in index.html" }
  $jsPath = $m.Groups[1].Value

  # make absolute if needed
  if ($jsPath -notmatch '^https?://') {
    $left  = $Site.TrimEnd('/')
    $right = $jsPath.TrimStart('/')
    $jsUrl = "$left/$right"
  } else {
    $jsUrl = $jsPath
  }
  Show $true "Found bundle JS: $jsUrl"
}
catch {
  Show $false "Parse index.html failed: $($_.Exception.Message)"
  return
}

# ---------- 4) Download the bundle and check which backend it calls ----------
try {
  $bundle = Invoke-WebRequest $jsUrl -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
  $backendHost = ([Uri]$Backend).Host
  $hasBackend  = $bundle.Content -match [regex]::Escape($backendHost)
  $hasRelative = $bundle.Content -match "fetch\(\s*`'/?api/"

  Show $hasBackend  "Bundle contains backend host '$backendHost' = $hasBackend"
  Show $hasRelative "Bundle also uses relative '/api/*' = $hasRelative"

  if (-not $hasBackend) {
    Write-Host ""
    Write-Host "Your Render Static Site build probably did NOT bake VITE_BACKEND_URL." -ForegroundColor Yellow
    Write-Host "Fix: In Render -> Static Site -> Environment, keep ONLY:" -ForegroundColor Yellow
    Write-Host "  VITE_BACKEND_URL = $Backend" -ForegroundColor Cyan
    Write-Host "Then: Manual Deploy -> Clear build cache & deploy." -ForegroundColor Yellow
  }
}
catch {
  Show $false "Fetch bundle failed: $($_.Exception.Message)"
}

