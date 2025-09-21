param([string]$BackendUrl)
if (-not $BackendUrl) {
  Write-Host "Usage: .\verify-backend.ps1 -BackendUrl https://YOUR-APP.onrender.com" -ForegroundColor Yellow
  exit 1
}
function Test-EP([string]$u) {
  try {
    $r = Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 20
    Write-Host ("OK {0} -> {1} : {2}" -f $r.StatusCode, $u, $r.Content) -ForegroundColor Green
    return $true
  } catch {
    Write-Host ("ERROR -> {0} : {1}" -f $u, $_.Exception.Message) -ForegroundColor Red
    return $false
  }
}
$ok1 = Test-EP ($BackendUrl.TrimEnd('/') + "/health")
$ok2 = Test-EP ($BackendUrl.TrimEnd('/') + "/api/health")
if ($ok1 -and $ok2) {
  Write-Host "Both health endpoints OK. ✅" -ForegroundColor Green
  exit 0
} else {
  Write-Host "Something is off. Open Render logs and copy the last 40 lines after 'Start Command'." -ForegroundColor Magenta
  exit 2
}