$ErrorActionPreference = 'Stop'
function Ping($label,$url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
    Write-Host "$label: $($r.StatusCode) $($r.Content)"
  } catch { Write-Host "ERR $label: $($_.Exception.Message)" -ForegroundColor Red }
}

Ping "health" "http://localhost:8000/api/health"

$body = @{ q = "ping" } | ConvertTo-Json
try {
  $r = Invoke-WebRequest "http://localhost:8000/api/ask" -Method Post -ContentType "application/json" -Body $body
  Write-Host "ask: $($r.StatusCode) $($r.Content)"
} catch { Write-Host "ERR ask: $($_.Exception.Message)" -ForegroundColor Red }


