# scripts/render-check.ps1
[CmdletBinding()]
Param(
  [Parameter(Mandatory=$true)][string]$Backend,   # e.g. https://friday-xxxx.onrender.com
  [string]$Frontend = ""
)

$ErrorActionPreference = "Stop"

function Show($label, $ok) {
  $c = $(if ($ok) { "Green" } else { "Red" })
  Write-Host ("{0,-28} {1}" -f $label, ($(if ($ok) { "OK" } else { "FAIL" }))) -ForegroundColor $c
}

function Ping200($url) {
  try { (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200 } catch { $false }
}

Write-Host "=== Render probe: $Backend ===" -ForegroundColor Cyan

$ok1 = Ping200("$Backend/health")
$ok2 = Ping200("$Backend/api/health")
Show "/health" $ok1
Show "/api/health" $ok2

# Ask
try {
  $body = @{ prompt = "hello from render-check" } | ConvertTo-Json
  $r = Invoke-WebRequest "$Backend/api/ask" -Method Post -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 20
  $ok3 = ($r.StatusCode -eq 200)
} catch { $ok3 = $false }
Show "POST /api/ask" $ok3

# Session
try {
  $r2 = Invoke-WebRequest "$Backend/api/session" -Method Post -UseBasicParsing -TimeoutSec 20
  $ok4 = ($r2.StatusCode -eq 200)
} catch { $ok4 = $false }
Show "POST /api/session" $ok4

if ($Frontend) {
  Write-Host "`n=== Frontend probe: $Frontend ===" -ForegroundColor Cyan
  $ok5 = Ping200("$Frontend/health")
  $ok6 = Ping200("$Frontend/api/health")
  Show "GET /health (frontend)" $ok5
  Show "GET /api/health (frontend)" $ok6
}

