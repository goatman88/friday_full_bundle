# verify-backend.ps1
param(
  [string]$BackendUrl = "https://friday-099e.onrender.com"
)

function Test-Health([string]$url) {
  for ($i=1; $i -le 20; $i++) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method GET -TimeoutSec 8
      Write-Host ("OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
      return $true
    } catch {
      Write-Host ("Attempt {0}: {1}" -f $i, $_.Exception.Response.StatusDescription) -ForegroundColor Yellow
      Start-Sleep -Seconds 2
    }
  }
  Write-Host ("Gave up on {0}" -f $url) -ForegroundColor Red
  return $false
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
