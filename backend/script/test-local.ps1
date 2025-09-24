$ErrorActionPreference = "Stop"
$api = "http://localhost:8000"

function Show($label,$r) {
  "{0,-14} -> {1} {2}" -f $label,$r.StatusCode,$r.StatusDescription
}

Write-Host "🔎 Pinging backend..." -ForegroundColor Cyan
Show "/health"     (Invoke-WebRequest -Uri "$api/health" -UseBasicParsing)
Show "/api/health" (Invoke-WebRequest -Uri "$api/api/health" -UseBasicParsing)

$q = @{ q = "ping" } | ConvertTo-Json
$r = Invoke-WebRequest -Uri "$api/api/ask" -Method Post -ContentType "application/json" -Body $q
Show "POST /api/ask" $r
$r.Content | Write-Host

# Session
$s = Invoke-WebRequest -Uri "$api/api/session" -Method Post -ContentType "application/json" -Body "{}"
Show "POST /api/session" $s
$s.Content | Write-Host

# SDP (demo only; needs real SDP string if you plan to connect WebRTC)
$fake = @{ sdp = "v=0`r`no=fake" } | ConvertTo-Json
$r2 = Invoke-WebRequest -Uri "$api/api/sdp" -Method Post -ContentType "application/json" -Body $fake
Show "POST /api/sdp" $r2
$r2.Content | Write-Host
