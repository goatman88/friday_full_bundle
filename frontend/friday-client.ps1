<#
Usage examples:
  # from the folder where this file lives
  Set-ExecutionPolicy -Scope Process Bypass
  .\friday-client.ps1 -Base "https://friday-099e.onrender.com" -DoQuery:$true

Notes:
- Pass the ROOT site only as -Base (https://…onrender.com). This script will detect
  whether routes live under /api or not and pick the correct one automatically.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Base,                              # e.g. https://friday-099e.onrender.com  (root only)

  [string]$Collection = "default",
  [switch]$DoQuery = $false,                  # true to call /rag/query if exposed
  [string]$FileName = "demo.txt",
  [string]$ContentType = "text/plain",
  [string]$InlineText = "Hello from Friday via PowerShell"
)

# ---------------- helpers ----------------
function Join-Url {
  param([string]$a, [string]$b)
  if (-not $a) { return $b }
  if (-not $b) { return $a }
  $aTrim = $a.TrimEnd('/')
  $bTrim = $b.TrimStart('/')
  return "$aTrim/$bTrim"
}

function Invoke-WithRetry {
  param([scriptblock]$Action, [int]$Retries = 5)
  for ($i = 1; $i -le $Retries; $i++) {
    try { return & $Action }
    catch {
      if ($i -lt $Retries) {
        Write-Host ("Transient error, retrying in {0} ms... ({1}/{2})" -f ($i*1000), $i, $Retries) -ForegroundColor Yellow
        Start-Sleep -Milliseconds ($i*1000)
      } else { throw }
    }
  }
}

function Detect-ApiBase {
  param([string]$root)
  $candidates = @(
    Join-Url $root "api",
    $root
  )
  foreach ($cand in $candidates) {
    $probe = Join-Url $cand "health"
    try {
      $resp = Invoke-RestMethod -Uri $probe -Method GET -TimeoutSec 10
      Write-Host ("Health OK at {0}" -f $probe) -ForegroundColor Green
      return $cand
    } catch {
      # some backends 404 the health page but still exist; try /docs as a hint
      try {
        $code = (Invoke-WebRequest -Uri (Join-Url $cand "docs") -UseBasicParsing -Method GET | Select-Object -ExpandProperty StatusCode) 2>$null
        if ($code -ge 200 -and $code -lt 500) {
          Write-Host ("Docs present at {0}, assuming base {1}" -f (Join-Url $cand "docs"), $cand) -ForegroundColor Yellow
          return $cand
        }
      } catch {}
    }
  }
  throw "Could not find a working API base under $root (tried '/api' and root)."
}

# ---------- start ----------
Write-Host "`n== Friday client ==" -ForegroundColor Cyan

# 0) Normalize the root (strip trailing slash)
$Base = $Base.TrimEnd('/')

# 1) Detect whether routes are under /api or not
Write-Host "`n[1] Detecting API base..." -ForegroundColor Cyan
$ApiBase = Detect-ApiBase -root $Base
Write-Host ("Using API base: {0}" -f $ApiBase) -ForegroundColor Green

# 2) Show endpoints we’ll use
$healthUrl  = Join-Url $ApiBase "health"
$presignUrl = Join-Url $ApiBase "rag/upload_url"
$confirmUrl = Join-Url $ApiBase "rag/confirm_upload"
$queryUrl   = Join-Url $ApiBase "rag/query"
Write-Host ("`nEndpoints:`n  health : {0}`n  upload : {1}`n  confirm: {2}`n  query  : {3}" -f $healthUrl,$presignUrl,$confirmUrl,$queryUrl) -ForegroundColor DarkGray

# 3) Health
Write-Host "`n[2] Health check..." -ForegroundColor Cyan
try {
  $health = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 10
  Write-Host ("Health: {0}" -f ($health | ConvertTo-Json -Depth 3)) -ForegroundColor Green
} catch {
  $msg = $_.Exception.Message
  Write-Host ("Health check failed: {0}. Continuing anyway..." -f $msg) -ForegroundColor Yellow
}

# 4) Ask backend for S3 pre-signed URL
Write-Host "`n[3] Requesting pre-signed URL..." -ForegroundColor Cyan
$presignReq = @{
  filename     = $FileName
  content_type = $ContentType
}
$presign = Invoke-WithRetry { Invoke-RestMethod -Uri $presignUrl -Method POST -ContentType "application/json" -Body ($presignReq | ConvertTo-Json -Depth 5) }
Write-Host ("Presign response:`n{0}" -f ($presign | ConvertTo-Json -Depth 5)) -ForegroundColor Green

# Validate expected fields
if (-not $presign.put_url -or -not $presign.s3_uri) {
  throw "Presign response missing expected fields. Got: $($presign | ConvertTo-Json -Depth 5)"
}
$putUrl = [string]$presign.put_url
$s3Uri  = [string]$presign.s3_uri

# 5) PUT the content to S3
Write-Host "`n[4] Uploading to S3 (PUT to presigned url)..." -ForegroundColor Cyan
$bytes = [System.Text.Encoding]::UTF8.GetBytes($InlineText)
Invoke-WebRequest -Uri $putUrl -Method PUT -Body $bytes -ContentType $ContentType | Out-Null
Write-Host "Upload complete." -ForegroundColor Green

# 6) Confirm / index
Write-Host "`n[5] Confirm upload (index)..." -ForegroundColor Cyan
$confirmReq = @{
  s3_uri      = $s3Uri
  title       = "demo_file"
  external_id = "demo_1"
  metadata    = @{ collection = $Collection; tags = @("test"); source = "cli" }
  chunk       = @{ size = 1200; overlap = 150 }
}
$confirm = Invoke-WithRetry { Invoke-RestMethod -Uri $confirmUrl -Method POST -ContentType "application/json" -Body ($confirmReq | ConvertTo-Json -Depth 6) }
Write-Host ("Confirm response:`n{0}" -f ($confirm | ConvertTo-Json -Depth 6)) -ForegroundColor Green

# 7) Optional query (only if exposed and user asked)
$hasQuery = $false
try {
  $probe = Invoke-WebRequest -Uri $queryUrl -Method OPTIONS -TimeoutSec 8 -UseBasicParsing
  if ($probe.StatusCode -in 200,204,405,403) { $hasQuery = $true }
} catch {}

if ($DoQuery -and $hasQuery) {
  Write-Host "`n[6] Querying the index..." -ForegroundColor Cyan
  $q = @{ q = "what did the fox do?" }
  try {
    $resp = Invoke-WithRetry { Invoke-RestMethod -Uri $queryUrl -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5) }
    Write-Host ("Query response:`n{0}" -f ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Green
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    Write-Host "Query failed with HTTP $code" -ForegroundColor DarkYellow
    throw
  }
} elseif (-not $DoQuery) {
  Write-Host "[6] Query step skipped (user disabled)." -ForegroundColor DarkYellow
} else {
  Write-Host "[6] Query step skipped (no /rag/query route exposed)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green



