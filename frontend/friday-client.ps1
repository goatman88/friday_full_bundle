<# friday-client.ps1
   Simple RAG client for your Friday API on Render.
   Usage:
     Set-ExecutionPolicy -Scope Process Bypass
     .\friday-client.ps1 -Base "https://friday-099e.onrender.com" -DoQuery:$true
#>

param(
  [Parameter(Mandatory=$true)]
  [string] $Base,                  # e.g. https://friday-099e.onrender.com  (no trailing slash, no /api)
  [switch] $DoQuery = $false       # run the optional /rag/query step if the route exists
)

# ----- helpers ---------------------------------------------------------------
function Show-Endpoint($name, $url) {
  # NOTE: -f placeholders must be numbered; also escape braces by doubling if you ever need them
  Write-Host ("{0,-8} {1}" -f $name, $url) -ForegroundColor DarkGray
}

function Get-JsonBody([object]$o) { $o | ConvertTo-Json -Depth 6 }

function Invoke-WithRetry([scriptblock] $Action, [int]$Retries = 5) {
  for ($i=1; $i -le $Retries; $i++) {
    try { return & $Action }
    catch {
      if ($i -eq $Retries) { throw }
      Write-Host ("Transient error, retrying in {0}s... ({1}/{2})" -f $i,$i,$Retries) -ForegroundColor Yellow
      Start-Sleep -Seconds $i
    }
  }
}

# Ensure TLS 1.2 for older Windows PowerShell
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# ----- build normalized endpoints -------------------------------------------
$apiBase = if ($Base.TrimEnd('/') -match '/api$') { $Base.TrimEnd('/') } else { "$($Base.TrimEnd('/'))/api" }
$healthEP = "$apiBase/health"
$uploadEP = "$apiBase/rag/upload_url"
$putEP    = "$apiBase/rag/upload_put/{token}"
$confirmEP= "$apiBase/rag/confirm_upload"
$queryEP  = "$apiBase/rag/query"

Write-Host "`n== Friday client ==" -ForegroundColor Cyan
Write-Host ("Using base: [{0}]" -f $apiBase) -ForegroundColor Cyan
Write-Host "Endpoints:" -ForegroundColor DarkGray
Show-Endpoint "health :" $healthEP
Show-Endpoint "upload :" $uploadEP
Show-Endpoint "put    :" $putEP
Show-Endpoint "confirm:" $confirmEP
Show-Endpoint "query  :" $queryEP
Write-Host ("Raw health URL: {0}" -f $healthEP) -ForegroundColor DarkGray

# ----- 1) Health -------------------------------------------------------------
Write-Host "`n[1] Health check..." -ForegroundColor Cyan
try {
  $resp = Invoke-WebRequest -Uri $healthEP -Method GET -UseBasicParsing
  if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
    Write-Host ("Health: {0}" -f ($resp.Content)) -ForegroundColor Green
  } else {
    throw "Unexpected status: $($resp.StatusCode)"
  }
}
catch {
  # show server body if available
  $body = $_.Exception.Response | ForEach-Object { (New-Object IO.StreamReader($_.GetResponseStream())).ReadToEnd() }
  if ($body) { Write-Host ("Body: {0}" -f $body) -ForegroundColor DarkGray }
  Write-Host "Health check FAILED. Make sure your service is live and routes are under /api." -ForegroundColor Red
  Write-Host ("Tip: open in browser: {0}" -f $healthEP) -ForegroundColor Yellow
  exit 1
}

# ----- 2) Get presigned upload URL ------------------------------------------
Write-Host "`n[2] Get upload URL..." -ForegroundColor Cyan
$req = @{ filename = "demo.txt"; content_type = "text/plain" }
$pre = Invoke-WithRetry { Invoke-RestMethod -Uri $uploadEP -Method POST -ContentType "application/json" -Body (Get-JsonBody $req) }
$putUrl = $pre.put_url
$token  = $pre.token
if (-not $putUrl -or -not $token) { throw "Presign response missing put_url or token. Got: $($pre | Get-JsonBody)" }
Write-Host "Presign OK." -ForegroundColor Green

# ----- 3) PUT bytes to S3 (inline content) ----------------------------------
Write-Host "`n[3] Upload to S3..." -ForegroundColor Cyan
$bytes = [System.Text.Encoding]::UTF8.GetBytes("Hello from Friday via PowerShell")
Invoke-WebRequest -Uri $putUrl -Method PUT -Body $bytes -ContentType "text/plain" -UseBasicParsing | Out-Null
Write-Host "Upload complete." -ForegroundColor Green

# ----- 4) Confirm / index ----------------------------------------------------
Write-Host "`n[4] Confirm upload..." -ForegroundColor Cyan
$confirmReq = @{
  s3_uri      = "s3://demo"
  title       = "demo_file"
  external_id = "demo_1"
  metadata    = @{ collection = "default"; tags = @("test"); source = "cli" }
  chunk       = @{ size = 1200; overlap = 150 }
}
$confirm = Invoke-WithRetry { Invoke-RestMethod -Uri $confirmEP -Method POST -ContentType "application/json" -Body (Get-JsonBody $confirmReq) }
Write-Host ("Confirm response: {0}" -f ($confirm | Get-JsonBody)) -ForegroundColor Green

# ----- 5) Optional query (if route exists and user asked) --------------------
$hasQuery = $false
if ($DoQuery) {
  try {
    $probe = Invoke-WebRequest -Uri $queryEP -Method OPTIONS -TimeoutSec 8 -UseBasicParsing
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
      Write-Host ("Query failed with HTTP {0}" -f $code) -ForegroundColor DarkYellow
      throw
    }
  } else {
    Write-Host "[5] Query step skipped (no /rag/query route exposed)." -ForegroundColor DarkYellow
  }
} else {
  Write-Host "[5] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green





