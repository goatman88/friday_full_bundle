param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Site
)

function Show([bool]$ok,[string]$msg){
  if($ok){ Write-Host "[PASS] " -ForegroundColor Green -NoNewLine } else { Write-Host "[FAIL] " -ForegroundColor Red -NoNewLine }
  Write-Host $msg
}

Write-Host "=== Friday Frontend Doctor (auto-check) ===" -ForegroundColor Cyan
Write-Host ("Backend : {0}" -f $Backend)
Write-Host ("Static  : {0}" -f $Site)

# 1) CORS preflight OPTIONS (simulates browser)
try{
  $opt = Invoke-WebRequest -Method Options -Uri "$Backend/api/health" `
    -Headers @{ "Origin"=$Site; "Access-Control-Request-Method"="GET" } `
    -TimeoutSec 20 -ErrorAction Stop
  $acao = $opt.Headers['access-control-allow-origin']
  Show (($opt.StatusCode -eq 200) -and $acao) ("CORS preflight ok (ACAO=$acao, status=$($opt.StatusCode))")
}catch{ Show $false ("CORS preflight failed: $($_.Exception.Message)") }

# 2) GET with Origin (what browsers do after preflight)
try{
  $get = Invoke-WebRequest -Method GET -Uri "$Backend/api/health" -Headers @{ "Origin"="$Site" } -TimeoutSec 20 -ErrorAction Stop
  Show (($get.StatusCode -eq 200) -and ($get.Content -match '"status"\s*:\s*"ok"')) ("GET ok (status=$($get.StatusCode))")
}catch{ Show $false ("GET with Origin failed: $($_.Exception.Message)") }

# 3) Locate the deployed bundle JS from index.html
$jsUrl = $null
try{
  $index = Invoke-WebRequest $Site -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop
  $m = [regex]::Match($index.Content,'<script[^>]+type="module"[^>]+src="([^"]+\.js)"','IgnoreCase')
  if ($m.Success) {
    $jsPath = $m.Groups[1].Value
    if ($jsPath -notmatch '^https?://') { $Site = $Site.TrimEnd('/'); $right = $jsPath.TrimStart('/'); $jsUrl = "$Site/$right" } else { $jsUrl = $jsPath }
    Show $true ("Found bundle JS: $jsUrl")
  } else { Show $false "Could not find bundle JS <script> in index.html" }
}catch{ Show $false ("Parse index.html failed: $($_.Exception.Message)") }

# 4) Inspect the bundle for baked host + relative '/api'
if ($jsUrl){
  try{
    $bundle = Invoke-WebRequest $jsUrl -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop
    $backendHost = ([Uri]$Backend).Host
    $hasHost   = $bundle.Content -match ([regex]::Escape($backendHost))
    $hasRel    = $bundle.Content -match "fetch\(\s*['""]\/api/"
    Show $hasHost   "Bundle DOES include backend host (baked absolute URL)"
    Show (-not $hasRel) "No relative '/api/*' fetches found"
  }catch{ Show $false ("Fetch bundle failed: $($_.Exception.Message)") }
}

Write-Host "`n--- Final guidance ---" -ForegroundColor Cyan
if (-not $hasHost) {
  Write-Host ("Result: Your deployed bundle does NOT include the backend host.  Keep ONLY this key in Render (Static Site) Environment: VITE_BACKEND_URL = {0}" -f $Backend) -ForegroundColor Yellow
  Write-Host "Then Manual Deploy → Clear build cache & Deploy (IMPORTANT)." -ForegroundColor Yellow
}elseif ($hasRel) {
  Write-Host "Result: Bundle still contains relative '/api/*' calls." -ForegroundColor Yellow
  Write-Host "Ensure code uses the baked env var, e.g. fetch(`${import.meta.env.VITE_BACKEND_URL}/api/...`)." -ForegroundColor Green
}else{
  Write-Host "Result: Looks good. The bundle references the backend host and uses absolute URLs." -ForegroundColor Green
}
