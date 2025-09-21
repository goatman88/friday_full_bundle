param(
  [string]$BackendUrl = "https://friday-099e.onrender.com",
  [string]$FrontendOrigin = "http://localhost:5173"
)

function Test-Endpoint([string]$url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method GET -TimeoutSec 10
    Write-Host ("OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
    return $true
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    $desc = $_.Exception.Response.StatusDescription
    Write-Host ("ERROR {0} {1}" -f $code, $desc) -ForegroundColor Red
    return $false
  }
}

function Test-With-Origin([string]$url, [string]$origin) {
  Write-Host ("`nSimulating browser from Origin: {0}" -f $origin) -ForegroundColor Cyan
  # Preflight OPTIONS
  try {
    $pre = Invoke-WebRequest -UseBasicParsing -Uri $url -Method Options `
      -Headers @{ "Origin"=$origin; "Access-Control-Request-Method"="GET" } -TimeoutSec 10
    Write-Host ("Preflight OK {0}" -f $pre.StatusCode) -ForegroundColor DarkGreen
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    $desc = $_.Exception.Response.StatusDescription
    Write-Host ("Preflight ERROR {0} {1}" -f $code, $desc) -ForegroundColor Yellow
  }

  # Actual GET with Origin
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method GET `
      -Headers @{ "Origin"=$origin } -TimeoutSec 10
    Write-Host ("GET OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    $desc = $_.Exception.Response.StatusDescription
    Write-Host ("GET ERROR {0} {1}" -f $code, $desc) -ForegroundColor Red
  }
}

$health1 = ($BackendUrl.TrimEnd('/') + "/health")
$health2 = ($BackendUrl.TrimEnd('/') + "/api/health")

Write-Host ("Checking {0} ..." -f $health1) -ForegroundColor Cyan
$ok1 = Test-Endpoint $health1

Write-Host ("`nChecking {0} ..." -f $health2) -ForegroundColor Cyan
$ok2 = Test-Endpoint $health2

# Simulate the frontend origin (local Vite and your deployed domain if you have it)
Test-With-Origin $health1 $FrontendOrigin
Test-With-Origin $health2 $FrontendOrigin

# Optional: also test your deployed static site origin if you have it
# Test-With-Origin $health1 "https://YOUR-STATIC-SITE-DOMAIN"
# Test-With-Origin $health2 "https://YOUR-STATIC-SITE-DOMAIN"
