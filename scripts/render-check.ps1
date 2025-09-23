# scripts/render-check.ps1
param(
  [Parameter(Mandatory=$false)][string]$Backend = $env:FRI_BACKEND_URL
)

if ([string]::IsNullOrWhiteSpace($Backend)) {
  Write-Error "Provide -Backend https://your-backend.onrender.com or set FRI_BACKEND_URL"
  exit 1
}

function Get-Status([string]$u) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing
    return "$($r.StatusCode) OK"
  } catch {
    try { return "$($_.Exception.Response.StatusCode.value__) ERR" } catch { return "ERR $($_.Exception.Message)" }
  }
}

Write-Host "Checking $Backend ..." -ForegroundColor Yellow
" /health             => $(Get-Status "$Backend/health")"
" /api/health         => $(Get-Status "$Backend/api/health")"

# /session (POST)
try {
  $r = Invoke-WebRequest -Uri "$Backend/session" -Method Post -UseBasicParsing
  Write-Host " /session (POST)   => $($r.StatusCode) OK"
} catch {
  try { Write-Host " /session (POST)   => $($_.Exception.Response.StatusCode.value__) ERR" -ForegroundColor Red }
  catch { Write-Host " /session (POST)   => ERR $($_.Exception.Message)" -ForegroundColor Red }
}

# /api/ask (POST)
try {
  $body = @{ prompt = "diagnostic ping"; latency = "fast" } | ConvertTo-Json
  $r = Invoke-WebRequest -Uri "$Backend/api/ask" -Method Post -ContentType "application/json" -Body $body -UseBasicParsing
  Write-Host " /api/ask (POST)   => $($r.StatusCode) OK"
} catch {
  try { Write-Host " /api/ask (POST)   => $($_.Exception.Response.StatusCode.value__) ERR" -ForegroundColor Red }
  catch { Write-Host " /api/ask (POST)   => ERR $($_.Exception.Message)" -ForegroundColor Red }
}

# Optional extras
" /transcript (GET)   => $(Get-Status "$Backend/transcript")"
try {
  $r = Invoke-WebRequest -Uri "$Backend/transcript" -Method Delete -UseBasicParsing
  Write-Host " /transcript (DEL)  => $($r.StatusCode) OK"
} catch {
  try { Write-Host " /transcript (DEL)  => $($_.Exception.Response.StatusCode.value__) ERR" -ForegroundColor Red }
  catch { Write-Host " /transcript (DEL)  => ERR $($_.Exception.Message)" -ForegroundColor Red }
}
