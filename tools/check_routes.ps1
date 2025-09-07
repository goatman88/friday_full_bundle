param()

if (-not $env:FRIDAY_BASE) { throw "Set `FRIDAY_BASE` to your Render URL (no trailing slash)" }
if (-not $env:API_TOKEN)   { throw "Set `API_TOKEN` to your API token" }

$headers = @{
  Authorization = "Bearer $($env:API_TOKEN)"
  Accept        = "application/json"
}

$uri = "$($env:FRIDAY_BASE)/__routes"
Write-Host "GET $uri"
try {
  $resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
  $resp | ConvertTo-Json -Depth 6 | Out-String | Write-Host
} catch {
  Write-Host ($_ | Out-String)
  throw
}

