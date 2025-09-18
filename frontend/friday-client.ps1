<#  Friday RAG client (robust)
    Usage:
      Set-ExecutionPolicy -Scope Process Bypass
      .\friday-client.ps1 -Base "https://friday-099e.onrender.com" -DoQuery:$true
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$Base,                          # e.g. https://friday-099e.onrender.com  (no trailing slash)
  [switch]$DoQuery = $false,              # run /rag/query if present
  [string]$QueryText = 'what did the fox do?'
)

# ---------- Helpers ----------
function Normalize-Base([string]$b) {
  $b = $b.Trim()
  if ($b.EndsWith('/')) { $b = $b.TrimEnd('/') }
  # Accept either root or /api, normalize to /api
  if ($b -match '/api$') { return $b }
  return "$b/api"
}

function Join-Url([string]$left, [string]$right) {
  $left = $left.TrimEnd('/')
  $right = $right.TrimStart('/')
  return "$left/$right"
}

# Ensure TLS 1.2+
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# A tiny retry wrapper (network flakes)
function Invoke-WithRetry {
  param([scriptblock]$Action, [int]$Retries = 3)
  for ($i=1; $i -le $Retries; $i++) {
    try { return & $Action }
    catch {
      if ($i -lt $Retries) { Start-Sleep -Milliseconds 600 }
      else { throw }
    }
  }
}

# ---------- Derive endpoints ----------
$apiBase   = Normalize-Base $Base
$healthUrl = Join-Url $apiBase 'health'

$uploadEP  = Join-Url $apiBase 'rag/upload_url'
$putEP     = Join-Url $apiBase 'rag/upload_put/{token}'
$confirmEP = Join-Url $apiBase 'rag/confirm_upload'
$queryEP   = Join-Url $apiBase 'rag/query'

Write-Host "`n== Friday client ==" -ForegroundColor Cyan
Write-Host ("Using base: [{0}]" -f $apiBase) -ForegroundColor Gray
Write-Host "Endpoints:" -ForegroundColor DarkGray
Write-Host ("  health : {0}" -f $healthUrl)  -ForegroundColor DarkGray
Write-Host ("  upload : {0}" -f $uploadEP)   -ForegroundColor DarkGray
Write-Host ("  put    : {0}" -f $putEP)      -ForegroundColor DarkGray
Write-Host ("  confirm: {0}" -f $confirmEP)  -ForegroundColor DarkGray
Write-Host ("  query  : {0}" -f $queryEP)    -ForegroundColor DarkGray

# Extra visibility if a stray space/newline sneaks in
Write-Host ("Raw health URL (quoted): '{0}'" -f $healthUrl.Replace("`n","⏎").Replace("`r","␍")) -ForegroundColor DarkGray

# ---------- STEP 1: Health ----------
Write-Host "`n[1] Health check..." -ForegroundColor Cyan
try {
  $headers = @{ 'Accept'='application/json'; 'User-Agent'='FridayPSClient/1.0' }
  $health = Invoke-WithRetry { Invoke-RestMethod -Uri $healthUrl -Headers $headers -Method GET }
  Write-Host ("OK -> {0}" -f ($health | ConvertTo-Json -Depth 3)) -ForegroundColor Green
}
catch {
  Write-Host "Health check FAILED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Tip: Copy this into your browser: $healthUrl" -ForegroundColor Yellow
  return
}

# ---------- STEP 2: (Optional) Query if route exists and user asked ----------
if ($DoQuery) {
  Write-Host "`n[2] Query probe..." -ForegroundColor Cyan
  $hasQuery = $false
  try {
    # An OPTIONS that returns either 200/204/405/403 proves the path exists
    $probe = Invoke-WebRequest -Uri $queryEP -Method OPTIONS -TimeoutSec 8 -UseBasicParsing -Headers @{ 'User-Agent'='FridayPSClient/1.0' }
    if ($probe.StatusCode -in 200,204,405,403) { $hasQuery = $true }
  }
  catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    if ($code -in 200,204,405,403) { $hasQuery = $true }
  }

  if ($hasQuery) {
    Write-Host "[2] Querying the index..." -ForegroundColor Cyan
    $q = @{ q = $QueryText }
    try {
      $resp = Invoke-WithRetry {
        Invoke-RestMethod -Uri $queryEP -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5) -Headers $headers
      }
      Write-Host ("Query response: {0}" -f ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Green
    }
    catch {
      $code = $_.Exception.Response.StatusCode.value__ 2>$null
      Write-Host "Query failed with HTTP $code" -ForegroundColor DarkYellow
      throw
    }
  }
  else {
    Write-Host "[2] Query step skipped (no /rag/query route exposed)." -ForegroundColor DarkYellow
  }
}
else {
  Write-Host "[2] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green




