param(
  [Parameter(Mandatory = $true)]
  [string]$Base,                         # e.g. https://friday-099e.onrender.com  (no trailing slash needed)
  [string]$Collection = "default",
  [switch]$DoQuery = $false,             # set to -DoQuery:$true if your API exposes /rag/query
  [string]$FileName = "demo.txt",
  [string]$ContentType = "text/plain",
  [string]$InlineText = "Hello from Friday via PowerShell"
)

# ---------- helpers ----------
function Invoke-WithRetry {
  param([scriptblock]$Action, [int]$Retries = 5)
  for ($i = 1; $i -le $Retries; $i++) {
    try { return & $Action } catch {
      if ($i -lt $Retries) {
        Write-Host "Transient error, retrying in $i s... ($i/$Retries)" -ForegroundColor Yellow
        Start-Sleep -Seconds $i
      } else { throw }
    }
  }
}

function Test-Endpoint {
  param([string]$Url, [string]$Method = "GET")
  try {
    Invoke-WebRequest -Uri $Url -Method $Method -TimeoutSec 10 -ErrorAction Stop | Out-Null
    return $true
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    if ($code -in 401,403,405) { return $true } # exists but not allowed / method not allowed
    return $false
  }
}

function First-WorkingUrl {
  param([string[]]$Paths, [string]$Method = "GET")
  foreach ($p in $Paths) {
    $u = "$Base$p"
    if (Test-Endpoint -Url $u -Method $Method) { return $u }
  }
  return $null
}

# ---------- normalize $Base ----------
$Base = $Base.Trim()
if ($Base.EndsWith("/")) { $Base = $Base.TrimEnd("/") }
# If user passed ".../api", strip it; we add /api ourselves where appropriate
if ($Base -match "/api/?$") { $Base = $Base -replace "/api/?$","" }

Write-Host "Using base: $Base" -ForegroundColor DarkGray

# ---------- step 1: health ----------
$healthUrl = First-WorkingUrl @("/api/health","/health") "HEAD"
if (-not $healthUrl) { $healthUrl = "$Base/api/health" }  # best guess if probing failed

Write-Host "`n[1] Health check at $healthUrl ..." -ForegroundColor Cyan
try {
  $health = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 10
  Write-Host ("Health: {0}" -f ($health | ConvertTo-Json -Depth 3)) -ForegroundColor Green
} catch {
  Write-Host "Health check failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Tip: open $healthUrl in a browser. If it says 'Not Found', your backend isn't exposing that route." -ForegroundColor DarkYellow
  exit 1
}

# ---------- step 2: discover routes via OpenAPI (with fallbacks) ----------
$openapiUrl = First-WorkingUrl @("/openapi.json") "GET"
$confirmPath = $null; $queryPath = $null; $uploadPath = $null

if ($openapiUrl) {
  try {
    $spec = Invoke-RestMethod -Uri $openapiUrl -Method GET -TimeoutSec 10
    $paths = $spec.paths.PSObject.Properties.Name
    $confirmPath = $paths | Where-Object { $_ -match "/confirm_upload$" } | Select-Object -First 1
    $queryPath   = $paths | Where-Object { $_ -match "/rag/query$" -or $_ -match "/query$" } | Select-Object -First 1
    $uploadPath  = $paths | Where-Object { $_ -match "/upload_url$" } | Select-Object -First 1
  } catch {}
}

# Fallbacks if OpenAPI is private/missing or paths not found
if (-not $confirmPath) { $confirmPath = ("/api/rag/confirm_upload","/rag/confirm_upload" | Where-Object { Test-Endpoint "$Base$_" "OPTIONS" } | Select-Object -First 1) }
if (-not $queryPath)   { $queryPath   = ("/api/rag/query","/rag/query"                 | Where-Object { Test-Endpoint "$Base$_" "OPTIONS" } | Select-Object -First 1) }
if (-not $uploadPath)  { $uploadPath  = ("/api/rag/upload_url","/rag/upload_url"       | Where-Object { Test-Endpoint "$Base$_" "OPTIONS" } | Select-Object -First 1) }

$confirmUrl = if ($confirmPath) { "$Base$confirmPath" } else { $null }
$queryUrl   = if ($queryPath)   { "$Base$queryPath"   } else { $null }
$uploadUrl  = if ($uploadPath)  { "$Base$uploadPath"  } else { $null }

Write-Host ("`nResolved endpoints:`n  health : {0}`n  upload : {1}`n  confirm: {2}`n  query  : {3}" -f $healthUrl,$uploadUrl,$confirmUrl,$queryUrl) -ForegroundColor DarkGray

# ---------- step 3: presign + PUT ----------
$s3Uri = $null
if ($uploadUrl) {
  Write-Host "`n[2] Get presigned upload URL..." -ForegroundColor Cyan
  $presignReq = @{ filename = $FileName; content_type = $ContentType }
  $presign = Invoke-WithRetry { Invoke-RestMethod -Uri $uploadUrl -Method POST -ContentType "application/json" -Body ($presignReq | ConvertTo-Json) }

  # accept multiple possible field names/shapes
  $putUrl = $presign.put_url; if (-not $putUrl) { $putUrl = $presign.url }
  $s3Uri  = $presign.s3_uri;  if (-not $s3Uri)  { $s3Uri = $presign.s3; if (-not $s3Uri) { $s3Uri = $presign.uri } }

  if (-not $putUrl -or -not $s3Uri) {
    Write-Host "Presign response missing expected fields. Raw response:" -ForegroundColor Red
    $presign | Format-List
    exit 1
  }

  Write-Host "PUT -> $putUrl`nS3  -> $s3Uri" -ForegroundColor DarkGray
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($InlineText)
  Invoke-WebRequest -Uri $putUrl -Method PUT -Body $bytes -ContentType $ContentType | Out-Null
  Write-Host "Upload complete." -ForegroundColor Green
} else {
  Write-Host "Skip upload: no /upload_url route found." -ForegroundColor DarkYellow
}

# ---------- step 4: confirm/index ----------
if ($confirmUrl -and $s3Uri) {
  Write-Host "`n[3] Confirm / index ..." -ForegroundColor Cyan
  $confirmReq = @{
    s3_uri      = $s3Uri
    title       = "demo_file"
    external_id = "demo_1"
    metadata    = @{ collection = $Collection; tags = @("test"); source = "cli" }
    chunk       = @{ size = 1200; overlap = 150 }
  }

  $confirm = Invoke-WithRetry {
    Invoke-RestMethod -Uri $confirmUrl -Method POST -ContentType "application/json" -Body ($confirmReq | ConvertTo-Json -Depth 6)
  }
  Write-Host ("Confirm response: {0}" -f ($confirm | ConvertTo-Json -Depth 5)) -ForegroundColor Green
} else {
  Write-Host "Skip confirm: route not found or no s3_uri." -ForegroundColor DarkYellow
}

# ---------- step 5: query (optional) ----------
if ($DoQuery) {
  if ($queryUrl) {
    Write-Host "`n[4] Querying the index..." -ForegroundColor Cyan
    $q = @{ q = "what did the fox do?" }
    try {
      $resp = Invoke-WithRetry {
        Invoke-RestMethod -Uri $queryUrl -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5)
      }
      Write-Host "Query response:" -ForegroundColor Yellow
      $resp | Format-List
    } catch {
      $code = $_.Exception.Response.StatusCode.value__ 2>$null
      Write-Host "Query failed with HTTP $code" -ForegroundColor DarkYellow
      throw
    }
  } else {
    Write-Host "Query step skipped (no /rag/query route found)." -ForegroundColor DarkYellow
  }
} else {
  Write-Host "[5] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green


