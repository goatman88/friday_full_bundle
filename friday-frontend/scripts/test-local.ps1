# sanity checks
try {
  $s = iwr http://localhost:8000/health -UseBasicParsing
  "GET /health => $($s.StatusCode)"
} catch { "health failed: $($_.Exception.Message)" }
$body = @{ q = "ping" } | ConvertTo-Json
try {
  $r = iwr http://localhost:8000/api/ask -Method Post -ContentType "application/json" -Body $body -UseBasicParsing
  "POST /api/ask => $($r.StatusCode) $($r.Content)"
} catch { "ask failed: $($_.Exception.Message)" }
