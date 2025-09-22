param([string]$BackendUrl)

function Test-Health($u){
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing
    Write-Host ("OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
    return $true
  } catch { Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red; return $false }
}

if (-not $BackendUrl) { Write-Host "Usage: .\verify-backend.ps1 -BackendUrl https://YOUR.onrender.com" -ForegroundColor Yellow; exit 1 }
$u1 = ($BackendUrl.TrimEnd('/')) + "/health"
$u2 = ($BackendUrl.TrimEnd('/')) + "/api/health"
Write-Host ("Checking {0} ..." -f $u1) -ForegroundColor Yellow
$ok1 = Test-Health $u1
Write-Host ("Checking {0} ..." -f $u2) -ForegroundColor Yellow
$ok2 = Test-Health $u2
if ($ok1 -and $ok2) { Write-Host "Both health endpoints returned OK - you're good!" -ForegroundColor Green; exit 0 }
Write-Host "`nSomething is off. In Render -> Logs, copy the last ~40 lines after 'Start Command'." -ForegroundColor Magenta
exit 2






