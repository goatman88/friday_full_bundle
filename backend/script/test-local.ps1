$base = "http://localhost:8000"
"GET /health => " + (iwr "$base/health").Content
"GET /api/health => " + (iwr "$base/api/health").Content
$body = @{ q = "ping" } | ConvertTo-Json
"POST /api/ask => " + (iwr "$base/api/ask" -Method Post -ContentType "application/json" -Body $body).Content



