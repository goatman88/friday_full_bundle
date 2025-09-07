param(
  [string]$Title   = "Sample Note",
  [string]$Text,
  [string]$Source  = "manual",
  [string]$Query   = "What does the note say?",
  [string]$FilePath,
  [switch]$ShowContexts,
  [int]$TopK       = 3
)

# -- Guard rails --------------------------------------------------------------
if (-not $env:FRIDAY_BASE) { throw "Set `FRIDAY_BASE` to your Render URL (no trailing slash)" }
if (-not $env:API_TOKEN)   { throw "Set `API_TOKEN` to your API token" }

# -- Helpers ------------------------------------------------------------------
function Invoke-FridayPostJson {
  param(
    [string]$Uri,
    [hashtable]$Body
  )
  $headers = @{
    Authorization = "Bearer $($env:API_TOKEN)"
    "Content-Type" = "application/json"
  }
  try {
    Invoke-RestMethod -Method Post -Uri $Uri -Headers $headers -Body ($Body | ConvertTo-Json -Depth 6)
  } catch {
    Write-Host "`nERROR calling $Uri" -ForegroundColor Red
    Write-Host ($_ | Out-String) -ForegroundColor DarkRed
    throw
  }
}

function Show-Contexts {
  param([object[]]$Items)
  if (-not $Items) { return }
  $i = 0
  foreach ($c in $Items) {
    $i++
    $score   = '{0:n3}' -f ($c.score)
    $title   = $c.title
    $preview = $c.preview
    $id      = $c.id
    Write-Host ("`n[{0}] score={1}  title={2}" -f $i, $score, $title) -ForegroundColor Cyan
    if ($id)      { Write-Host ("   id: {0}" -f $id) -ForegroundColor DarkCyan }
    if ($preview) { Write-Host ("   preview: {0}" -f $preview) }
  }
  Write-Host ""
}

# -- Build note text ----------------------------------------------------------
if ($FilePath) {
  if (-not (Test-Path $FilePath)) { throw "File not found: $FilePath" }
  $Text = Get-Content -Path $FilePath -Raw -ErrorAction Stop
}

if (-not $Text) {
  # Reasonable default so the script "just works" if you forget -Text/-FilePath
  $Text = "Acme builds rockets and coffee machines."
  $Title = "Acme Note"
  $Source = "manual"
}

# -- 1) Index the note --------------------------------------------------------
Write-Host "`n🧩 Indexing a note..." -ForegroundColor Yellow
$indexBody = @{
  title  = $Title
  text   = $Text
  source = $Source
}

$indexUri = "$($env:FRIDAY_BASE)/api/rag/index"
$indexRes = Invoke-FridayPostJson -Uri $indexUri -Body $indexBody

# Friendly summary
if ($indexRes.ok) {
  $chars = $indexRes.chars
  $docId = $indexRes.indexed
  Write-Host ("OK: indexed {0} chars  (id: {1})" -f $chars, $docId) -ForegroundColor Green
} else {
  Write-Host ("Indexing response: " + ($indexRes | ConvertTo-Json -Depth 6)) -ForegroundColor DarkYellow
}

# -- 2) Query it --------------------------------------------------------------
Write-Host "`n🔎 Querying..." -ForegroundColor Yellow
$queryBody = @{
  question = $Query
  top_k    = $TopK
}
$queryUri = "$($env:FRIDAY_BASE)/api/rag/query"
$queryRes = Invoke-FridayPostJson -Uri $queryUri -Body $queryBody

# Friendly summary
if ($queryRes.ok) {
  Write-Host ("Answer: {0}" -f $queryRes.answer) -ForegroundColor Green
  if ($ShowContexts) {
    Show-Contexts -Items $queryRes.contexts
  }
} else {
  Write-Host ("Query response: " + ($queryRes | ConvertTo-Json -Depth 6)) -ForegroundColor DarkYellow
}

# -- Raw JSON block (handy for debugging/copying) -----------------------------
Write-Host "`n--- raw JSON (index) ---"
$indexRes | ConvertTo-Json -Depth 6 | Out-String | Write-Host
Write-Host "`n--- raw JSON (query) ---"
$queryRes | ConvertTo-Json -Depth 6 | Out-String | Write-Host






