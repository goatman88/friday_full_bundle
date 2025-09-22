$body = @{ session_id = "local-dev"; q = "Test streaming, say hello in 3 words" } | ConvertTo-Json
Invoke-WebRequest -Uri http://localhost:8000/api/ask/stream -Method POST -Body $body -ContentType "application/json" -UseBasicParsing | % Content
