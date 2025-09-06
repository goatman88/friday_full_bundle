# Run quick tests from PowerShell (uses env vars already set in PS session)
param()

if (-not $env:FRIDAY_BASE) { throw "Set `$env:FRIDAY_BASE to your Render URL (no trailing slash)" }
if (-not $env:API_TOKEN)   { throw "Set `$env:API_TOKEN to your API token" }

Write-Host "ok routes"
Invoke-RestMethod -Uri "$($env:FRIDAY_BASE)/__routes" `
  -Headers @{ Authorization = "Bearer $($env:API_TOKEN)"; "Content-Type"="application/json" } `
  -Method Get | Out-String | Write-Host

Write-Host "`nok reply"
$body = @{ message = "Hello Friday!" } | ConvertTo-Json
Invoke-RestMethod -Uri "$($env:FRIDAY_BASE)/chat" `
  -Headers @{ Authorization = "Bearer $($env:API_TOKEN)"; "Content-Type"="application/json" } `
  -Method Post -Body $body | Out-String | Write-Host
