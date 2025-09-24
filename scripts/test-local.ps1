$base = "http://localhost:8000"

"`n/health -> $(Invoke-WebRequest -Uri "$base/health").StatusCode"
"/api/health -> $(Invoke-WebRequest -Uri "$base/api/health").StatusCode"

$body = @{ q = "ping" } | ConvertTo-Json
$r = Invoke-WebRequest -Uri "$base/api/ask" -Method Post -ContentType "application/json" -Body $body
"`n/api/ask -> $($r.StatusCode) $($r.Content)"

# session (should be 401 if no OPENAI_API_KEY set)
try {
  $s = Invoke-WebRequest -Uri "$base/api/session" -Method Post
  "/api/session -> $($s.StatusCode)"
} catch { "/api/session -> ERROR $($_.Exception.Message)" }
