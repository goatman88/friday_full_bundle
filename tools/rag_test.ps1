[CmdletBinding()]
param(
  [string] $Title  = "Acme Note",
  [string] $Text   = "Acme builds rockets and coffee machines.",
  [string] $FilePath,
  [string] $Source = "manual",
  [string] $Query  = "What does Acme build?",
  [int]    $TopK   = 2,
  [switch] $ShowContexts
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $env:FRIDAY_BASE) { throw "Set `$env:FRIDAY_BASE to your Render base URL (no trailing slash)" }
if (-not $env:API_TOKEN)   { throw "Set `$env:API_TOKEN to your API token" }

$base = $env:FRIDAY_BASE.TrimEnd("/")
$headers = @{
  Authorization = "Bearer $($env:API_TOKEN)"
  "Content-Type" = "application/json"
}

# --- 1) Index a note ---
Write-Host "`n📥 Indexing note..."

if ($FilePath) {
  if (-not (Test-Path $FilePath)) { throw "File not found: $FilePath" }
  $Text = Get-Content -Raw -Path $FilePath
}

$indexBody = @{
  title  = $Title
  text   = $Text
  source = $Source
} | ConvertTo-Json

$indexUri = "$base/api/rag/index"
$indexResp = Invoke-RestMethod -Uri $indexUri -Headers $headers -Method Post -Body $indexBody
$indexResp | ConvertTo-Json -Depth 6 | Write-Host

# --- 2) Query it ---
Write-Host "`n🔎 Querying..."
$queryBody = @{ question = $Query; top_k = $TopK } | ConvertTo-Json
$queryUri = "$base/api/rag/query"
$qresp = Invoke-RestMethod -Uri $queryUri -Headers $headers -Method Post -Body $queryBody

# friendly line
if ($qresp.answer) {
  Write-Host "`nanswer"
  Write-Host "------"
  Write-Host $qresp.answer
}

# optional contexts
if ($ShowContexts -and $qresp.contexts) {
  Write-Host "`n--- contexts ---"
  $qresp.contexts | ForEach-Object {
    "{0}  score={1}  title={2}" -f $_.id,$_.score,$_.title | Write-Host
    if ($_.preview) { "  " + $_.preview | Write-Host }
  }
}

# return raw json too (useful for debugging)
$qresp | ConvertTo-Json -Depth 6 | Write-Host







