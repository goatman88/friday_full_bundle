param([string]$BackendUrl)
if (-not $BackendUrl) { Write-Host "Usage: .\verify-backend.ps1 -BackendUrl https://your-app.onrender.com" -ForegroundColor Yellow; exit 1 }

function Test-Health([string]$u) {
  try {
    Write-Host ("Checking {0} ..." -f $u) -ForegroundColor Yellow
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 20
    Write-Host ("OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
    return $true
  } catch {
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    return $false
  }
}

$u1 = $BackendUrl.TrimEnd('/') + "/health"
$u2 = $BackendUrl.TrimEnd('/') + "/api/health"
$ok1 = Test-Health $u1
$ok2 = Test-Health $u2
if ($ok1 -and $ok2) { Write-Host "Both health endpoints returned OK - you're good!" -ForegroundColor Green; exit 0 }
Write-Host "`nSomething is off. In Render → Logs, copy the last ~40 lines after 'Start Command'." -ForegroundColor Magenta
exit 2




