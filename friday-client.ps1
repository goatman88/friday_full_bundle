<#  Friday RAG PowerShell client
    Usage:
      Set-ExecutionPolicy -Scope Process Bypass
      .\friday-client.ps1 -Base "https://friday-099e.onrender.com" -DoQuery:$true
#>

param(
  [Parameter(Mandatory=$true)][string]$Base,
  [switch]$DoQuery = $false,          # set true only if /api/rag/query is exposed
  [string]$Collection = "default",
  [string]$FileName = "demo.txt",
  [string]$ContentType = "text/plain",
  [string]$InLineText = "Hello from Friday via PowerShell"
)

# ---------- helpers ----------
function Normalize-Root([string]$b) {
  $b = $b.Trim()
  # strip trailing slash
  if ($b.EndsWith("/")) { $b = $b.Substring(0, $b.Length-1) }
  # strip any /api if user pasted it
  if ($b.ToLower().EndsWith("/api")) { $b = $b.Substring(0, $b.Length-4) }
  return $b
}

function Join-Url([string]$l, [string]$r) {
  if ($l.EndsWith("/")) { $l = $l.Substring(0, $l.Length-1) }
  if ($r.StartsWith("/")) { $r = $r.Substring(1) }
  return "$l/$r"
}

function Invoke-WithRetry([ScriptBlock]$Action, [int]$Retries=6) {
  for ($i=1; $i -le $Retries; $i++) {
    try { return & $Action }
    catch {
      if ($i -lt $Retries) {
        Write-Host ("Transient error, retrying in {0} ms... ({1}/{2})" -f ($i*1000), $i, $Retries) -ForegroundColor Yellow
        Start-Sleep -Milliseconds ($i * 1000)
      } else { throw }
    }
  }
}

# ---------- compute endpoints ----------
$rootBase = Normalize-Root $Base
$apiBase  = Join-Url $rootBase "api"

$healthEP  = Join-Url $apiBase "health"           # preferred
$healthEP2 = Join-Url $rootBase "health"          # fallback
$docsEP    = Join-Url $rootBase "docs"

$uploadEP  = Join-Url $apiBase "rag/upload_url"
$putEP     = Join-Url $apiBase "rag/upload_put/{token}"
$confirmEP = Join-Url $apiBase "rag/confirm_upload"
$queryEP   = Join-Url $apiBase "rag/query"

Write-Host ""
Write-Host "== Friday client ==" -ForegroundColor Cyan
Write-Host ("Using base: [{0}]" -f (Join-Url $rootBase "api")) -ForegroundColor Gray
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor DarkGray
Write-Host ("  health : {0}" -f $healthEP) -ForegroundColor DarkGray
Write-Host ("  upload : {0}" -f $uploadEP) -ForegroundColor DarkGray
Write-Host ("  put    : {0}" -f $putEP   ) -ForegroundColor DarkGray
Write-Host ("  confirm: {0}" -f $confirmEP) -ForegroundColor DarkGray
Write-Host ("  query  : {0}" -f $queryEP ) -ForegroundColor DarkGray
Write-Host ("Raw health URL (quoted): '{0}'" -f $healthEP) -ForegroundColor DarkGray

# ---------- STEP 1 : health check (with fallback) ----------
Write-Host "`n[1] Health check..." -ForegroundColor Cyan
try {
  $resp = Invoke-WebRequest -Uri $healthEP -Method GET -UseBasicParsing
  if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
    Write-Host ("Health: {0}" -f $resp.Content) -ForegroundColor Green
  } else {
    throw "Health returned unexpected status: $($resp.StatusCode)"
  }
}
catch {
  # Try fallback /health at the root
  try {
    $resp2 = Invoke-WebRequest -Uri $healthEP2 -Method GET -UseBasicParsing
    if ($resp2.StatusCode -ge 200 -and $resp2.StatusCode -lt 300) {
      Write-Host ("Health (fallback /health): {0}" -f $resp2.Content) -ForegroundColor Green
    } else {
      throw "Fallback health unexpected status: $($resp2.StatusCode)"
    }
  }
  catch {
    Write-Host "Health check FAILED. Make sure your service is live and routes are under /api." -ForegroundColor Red
    Write-Host ("Tip: open in browser: {0}" -f $healthEP) -ForegroundColor Yellow
    exit 1
  }
}

# ---------- STEP 2 : get presigned PUT ----------
Write-Host "`n[2] Get presigned upload URL..." -ForegroundColor Cyan
$presignReq = @{
  filename     = $FileName
  content_type = $ContentType
}
$presign = Invoke-WithRetry { Invoke-RestMethod -Uri $uploadEP -Method POST -ContentType "application/json" -Body ($presignReq | ConvertTo-Json -Depth 5) }
if (-not $presign.put_url -or -not $presign.s3_uri) {
  throw "Presign response missing fields. Got: $($presign | ConvertTo-Json -Depth 5)"
}
$putUrl = $presign.put_url
$s3Uri  = $presign.s3_uri
Write-Host "Presign OK." -ForegroundColor Green

# ---------- STEP 3 : PUT content to S3 ----------
Write-Host "`n[3] PUT to presigned URL..." -ForegroundColor Cyan
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($InLineText)
Invoke-WebRequest -Uri $putUrl -Method PUT -Body $bodyBytes -ContentType $ContentType | Out-Null
Write-Host "Upload complete." -ForegroundColor Green

# ---------- STEP 4 : Confirm / index ----------
Write-Host "`n[4] Confirm upload (index)..." -ForegroundColor Cyan
$confirmReq = @{
  s3_uri      = $s3Uri
  title       = "demo_file"
  external_id = "demo_1"
  metadata    = @{ collection = $Collection; tags = @("test"); source = "cli" }
  chunk       = @{ size = 1200; overlap = 150 }
}
$confirm = Invoke-WithRetry { Invoke-RestMethod -Uri $confirmEP -Method POST -ContentType "application/json" -Body ($confirmReq | ConvertTo-Json -Depth 6) }
Write-Host ("Confirm response: {0}" -f ($confirm | ConvertTo-Json -Depth 5)) -ForegroundColor Green

# ---------- STEP 5 : Optional query ----------
if ($DoQuery) {
  # quick probe: OPTIONS (accepts 200/204/405/403 as “exists”)
  $hasQuery = $false
  try {
    $probe = Invoke-WebRequest -Uri $queryEP -Method OPTIONS -TimeoutSec 6 -UseBasicParsing
    if ($probe.StatusCode -in 200,204,405,403) { $hasQuery = $true }
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    if ($code -in 200,204,405,403) { $hasQuery = $true }
  }

  if ($hasQuery) {
    Write-Host "`n[5] Querying the index..." -ForegroundColor Cyan
    $q = @{ q = "what did the fox do?" }
    try {
      $resp = Invoke-WithRetry { Invoke-RestMethod -Uri $queryEP -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5) }
      Write-Host ("Query response: {0}" -f ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Green
    } catch {
      $code = $_.Exception.Response.StatusCode.value__ 2>$null
      Write-Host "Query failed with HTTP $code" -ForegroundColor DarkYellow
      throw
    }
  } else {
    Write-Host "[5] Query step skipped (no /api/rag/query route exposed)." -ForegroundColor DarkYellow
  }
} else {
  Write-Host "[5] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green




