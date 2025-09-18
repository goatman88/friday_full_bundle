<# ========================== Friday PowerShell Client ==========================
    Usage:
      Set-ExecutionPolicy -Scope Process Bypass
      .\friday-client.ps1 -Base "https://<your-app>.onrender.com" -DoQuery:$true

    Notes:
      - Always pass the *root* URL. Do NOT include /api — this script adds it.
      - If /api/health returns 404 in the browser, your backend isn’t exposing it.
        Fix the backend first; the client will keep failing otherwise.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Base,                          # e.g. https://friday-099e.onrender.com   (no /api)

  [switch]$DoQuery = $true,               # optional demo query if /api/rag/query exists

  # Future switches you can wire up later
  [switch]$VerboseEndpoints
)

# ---------- Helpers ----------
function Normalize-ApiBase([string]$root) {
  $r = $root.TrimEnd('/')
  if ($r -match '/api$') { return $r }
  return "$r/api"
}

function Invoke-WithRetry {
  param([scriptblock]$Action, [int]$Retries = 4)
  for ($i = 1; $i -le $Retries; $i++) {
    try   { return & $Action }
    catch {
      if ($i -lt $Retries) {
        Write-Host ("Transient error, retrying in {0}s… ({1}/{2})" -f $i, $i, $Retries) -ForegroundColor Yellow
        Start-Sleep -Seconds $i
      } else { throw }
    }
  }
}

function Get-HttpBodyIfAny($err) {
  try {
    if ($err.Exception.Response -and $err.Exception.Response.GetResponseStream) {
      $sr = New-Object IO.StreamReader($err.Exception.Response.GetResponseStream())
      return $sr.ReadToEnd()
    }
  } catch {}
  return $null
}

# ---------- Build endpoints ----------
$api = Normalize-ApiBase $Base
$healthEP  = "$api/health"
$uploadEP  = "$api/rag/upload_url"
$putEP     = "$api/rag/upload_put/{token}"
$confirmEP = "$api/rag/confirm_upload"
$queryEP   = "$api/rag/query"

Write-Host ""
Write-Host "== Friday client ==" -ForegroundColor Cyan
Write-Host ("Using base: [{0}]" -f $api) -ForegroundColor Gray
Write-Host "Endpoints:" -ForegroundColor DarkGray
"{0,-8} : {1}" -f "health",  $healthEP
"{0,-8} : {1}" -f "upload",  $uploadEP
"{0,-8} : {1}" -f "put",     $putEP
"{0,-8} : {1}" -f "confirm", $confirmEP
"{0,-8} : {1}" -f "query",   $queryEP
Write-Host ("Raw health URL (quoted): '{0}'" -f $healthEP) -ForegroundColor DarkGray
Write-Host ""

# ---------- STEP 1: Health ----------
Write-Host "[1] Health check…" -ForegroundColor Cyan
try {
  $resp = Invoke-WithRetry { Invoke-WebRequest -Uri $healthEP -Method GET -UseBasicParsing }
  if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
    Write-Host ("Health: {0}" -f $resp.Content) -ForegroundColor Green
  } else {
    Write-Host ("Unexpected status: {0}" -f $resp.StatusCode) -ForegroundColor Yellow
    Write-Host "Tip: open in browser: $healthEP" -ForegroundColor Yellow
    exit 1
  }
}
catch {
  $body = Get-HttpBodyIfAny $_
  if ($body) { Write-Host ("Body: {0}" -f $body) -ForegroundColor DarkGray }
  Write-Host "Health check FAILED. Make sure your service is live and routes are under /api." -ForegroundColor Red
  Write-Host "Tip: open in browser: $healthEP" -ForegroundColor Yellow
  exit 1
}

# ---------- STEP 2 (optional): Demo query ----------
if ($DoQuery) {
  # First probe the query endpoint so we don’t crash if it’s not exposed.
  $hasQuery = $false
  try {
    $probe = Invoke-WebRequest -Uri $queryEP -Method OPTIONS -TimeoutSec 8 -UseBasicParsing
    if ($probe.StatusCode -in 200,204,405,403) { $hasQuery = $true }
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    if ($code -in 200,204,405,403) { $hasQuery = $true }
  }

  if ($hasQuery) {
    Write-Host "`n[5] Querying the index…" -ForegroundColor Cyan
    $q = @{ q = "what did the fox do?" }
    try {
      $resp = Invoke-WithRetry {
        Invoke-RestMethod -Uri $queryEP -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5)
      }
      Write-Host ("Query response: {0}" -f ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Green
    }
    catch {
      $code = $_.Exception.Response.StatusCode.value__ 2>$null
      Write-Host ("Query failed with HTTP {0}" -f $code) -ForegroundColor DarkYellow
      $body = Get-HttpBodyIfAny $_
      if ($body) { Write-Host ("Body: {0}" -f $body) -ForegroundColor DarkGray }
      # Don’t exit — query is optional
    }
  } else {
    Write-Host "[5] Query step skipped (no /api/rag/query route exposed)." -ForegroundColor DarkYellow
  }
} else {
  Write-Host "[5] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green






