# verify-backend.ps1
param(
  [Parameter(Mandatory=$true)][string]$BackendUrl
)

function Test-Health($url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method GET -TimeoutSec 10
    "{0} {1}" -f $r.StatusCode, $r.Content | Write-Host -ForegroundColor Green
    return $true
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    $desc = $_.Exception.Response.StatusDescription 2>$null
    Write-Host ("Attempt: {0} => {1} {2}" -f (Get-Date), $code, $desc) -ForegroundColor Yellow
    return $false
  }
}

$h1 = ($BackendUrl.TrimEnd('/') + "/health")
$h2 = ($BackendUrl.TrimEnd('/') + "/api/health")

Write-Host "Checking $h1 ..." -ForegroundColor Cyan
$ok1 = $false; for ($i=1; $i -le 20 -and -not $ok1; $i++) { $ok1 = Test-Health $h1; if (-not $ok1) { Start-Sleep -Seconds 3 } }

Write-Host "Checking $h2 ..." -ForegroundColor Cyan
$ok2 = $false; for ($i=1; $i -le 20 -and -not $ok2; $i++) { $ok2 = Test-Health $h2; if (-not $ok2) { Start-Sleep -Seconds 3 } }

if ($ok1 -and $ok2) {
  Write-Host "`nBoth health endpoints returned OK — you're good!" -ForegroundColor Green
  exit 0
} else {
  Write-Host "`nSomething is off. Open Render logs and copy the last 40 lines after 'Start Command'." -ForegroundColor Magenta
  exit 1
}


$h1 = ($BackendUrl.TrimEnd('/') + "/health")
$h2 = ($BackendUrl.TrimEnd('/') + "/api/health")

Write-Host ("Checking {0}..." -f $h1) -ForegroundColor Cyan
$ok1 = Test-Health $h1

Write-Host ("Checking {0}..." -f $h2) -ForegroundColor Cyan
$ok2 = Test-Health $h2

if ($ok1 -and $ok2) {
  Write-Host "`nBoth health endpoints returned OK — you're good!" -ForegroundColor Green
} else {
  Write-Host "`nSomething is off. Open Render logs and copy the last 40 lines after 'Start Command'." -ForegroundColor Magenta
}
