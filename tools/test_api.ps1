param()

if (-not $env:FRIDAY_BASE) { throw "Set `$env:FRIDAY_BASE" }
if (-not $env:API_TOKEN)   { throw "Set `$env:API_TOKEN" }

Write-Host "Testing /__routes endpoint..."
Invoke-RestMethod -Uri "$($env:FRIDAY_BASE)/__routes" `
  -Headers @{ Authorization = "Bearer $($env:API_TOKEN)"; "Content-Type"="application/json" } `
  -Method Get | Out-String | Write-Host

Write-Host "`nTesting /chat endpoint..."
$body = @{ message = "Hello Friday!" } | ConvertTo-Json
Invoke-RestMethod -Uri "$($env:FRIDAY_BASE)/chat" `
  -Headers @{ Authorization = "Bearer $($env:API_TOKEN)"; "Content-Type"="application/json" } `
  -Method Post -Body $body | Out-String | Write-Host
