param(
  [string]$Title  = "Acme Note",
  [string]$Text   = "Acme builds rockets and coffee machines.",
  [string]$Source = "manual"
)

# --- sanity checks -----------------------------------------------------------
if (-not $env:FRIDAY_BASE) { throw "Set `$env:FRIDAY_BASE to your Render URL (no trailing slash)" }
if (-not $env:API_TOKEN)   { throw "Set `$env:API_TOKEN to your API token" }

# Build common headers once
$headers = @{
  Authorization = "Bearer $($env:API_TOKEN)"
  "Content-Type" = "application/json"
}

function Show-AsJson($obj) {
  try { $obj | ConvertTo-Json -Depth 10 }
  catch { "$obj" }
}

Write-Host "== 1) Index a note ==================================================="
$indexBody = @{
  title  = $Title
  text   = $Text
  source = $Source
} | ConvertTo-Json

try {
  $resp = Invoke-RestMethod -Method Post `
          -Uri "$($env:FRIDAY_BASE)/api/rag/index" `
          -Headers $headers -Body $indexBody
  Show-AsJson $resp | Write-Host
} catch {
  Write-Host "`nIndexing failed:" -ForegroundColor Red
  ($_ | Out-String) | Write-Host
  throw
}

Write-Host "`n== 2) Query it ======================================================"
$qBody = @{ question = "What does Acme build?" } | ConvertTo-Json
try {
  $qresp = Invoke-RestMethod -Method Post `
           -Uri "$($env:FRIDAY_BASE)/api/rag/query" `
           -Headers $headers -Body $qBody
  Show-AsJson $qresp | Write-Host
} catch {
  Write-Host "`nQuery failed:" -ForegroundColor Red
  ($_ | Out-String) | Write-Host
  throw
}

Write-Host "`nDone."




