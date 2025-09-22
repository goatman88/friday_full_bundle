param([string])

function Test-Health([string]) {
  try {
    Write-Host ("Checking {0} ..." -f ) -ForegroundColor Yellow
     = Invoke-WebRequest  -UseBasicParsing -TimeoutSec 15
    Write-Host ("OK {0} {1}" -f .StatusCode, .Content) -ForegroundColor Green
    return True
  } catch {
    Write-Host ("ERROR: {0}" -f .Exception.Message) -ForegroundColor Red
    return False
  }
}

if (-not ) {
  Write-Host "Usage: .\verify-backend.ps1 -BackendUrl https://YOUR-APP.onrender.com" -ForegroundColor Yellow
  exit 1
}

 = (.TrimEnd('/')) + "/health"
 = (.TrimEnd('/')) + "/api/health"

 = Test-Health 
 = Test-Health 

if ( -and ) {
  Write-Host "Both health endpoints returned OK — you're good!" -ForegroundColor Green
  exit 0
} else {
  Write-Host "
Something is off. In Render → Logs, copy the last ~40 lines after 'Start Command'." -ForegroundColor Magenta
  exit 2
}
