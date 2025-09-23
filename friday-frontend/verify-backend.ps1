param([Parameter(Mandatory=$true)][string]$BackendUrl)
$ErrorActionPreference = "Stop"
function Test-Health($u){
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 8
    if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { return $true }
  } catch { }
  return $false
}
$u1 = ($BackendUrl.TrimEnd('/')) + "/health"
$u2 = ($BackendUrl.TrimEnd('/')) + "/api/health"
Write-Host ("Checking {0}" -f $u1) -ForegroundColor Yellow
$ok1 = Test-Health $u1
Write-Host ("Checking {0}" -f $u2) -ForegroundColor Yellow
$ok2 = Test-Health $u2
if ($ok1 -and $ok2) { Write-Host "OK: both health endpoints are good ✔" -ForegroundColor Green; exit 0 }
Write-Host "ERROR: one or both health endpoints failed." -ForegroundColor Red; exit 2
