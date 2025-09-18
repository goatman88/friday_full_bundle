param(
  [Parameter(Mandatory=$true)]
  [string]$Base,                 # e.g. https://friday-099e.onrender.com (NO trailing slash, NO /api)
  [switch]$DoQuery = $true       # set -DoQuery:$false to skip query
)

# --- helpers ---
function Invoke-WithRetry {
  param([scriptblock]$Action, [int]$Retries = 5)
  for ($i=1; $i -le $Retries; $i++) {
    try { return & $Action } catch {
      if ($i -lt $Retries) {
        Write-Host ("Transient error, retrying in {0}s... ({1}/{2})" -f $i,$i,$Retries) -ForegroundColor Yellow
        Start-Sleep -Milliseconds ($i * 1000)
      } else { throw }
    }
  }
}

# normalize & compose endpoints
$api = "$Base/api"
$healthEP  = "$api/health"
$uploadEP  = "$api/rag/upload_url"
$putEP     = "$api/rag/upload_put/{token}"
$confirmEP = "$api/rag/confirm_upload"
$queryEP   = "$api/rag/query"

Write-Host ""
Write-Host "== Friday client ==" -ForegroundColor Cyan
Write-Host ("Using base: [{0}]" -f $api)
Write-Host "Endpoints:" -ForegroundColor DarkGray
Write-Host ("  health : {0}" -f $healthEP)   -ForegroundColor DarkGray
Write-Host ("  upload : {0}" -f $uploadEP)   -ForegroundColor DarkGray
Write-Host ("  put    : {0}" -f $putEP)      -ForegroundColor DarkGray
Write-Host ("  confirm: {0}" -f $confirmEP)  -ForegroundColor DarkGray
Write-Host ("  query  : {0}" -f $queryEP)    -ForegroundColor DarkGray
Write-Host ("Raw health URL (quoted): '{0}'" -f $healthEP) -ForegroundColor DarkGray

# [1] Health
Write-Host "`n[1] Health check..." -ForegroundColor Cyan
try {
  $resp = Invoke-WebRequest -Uri $healthEP -Method GET -UseBasicParsing
  if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
    Write-Host ("Health: {0}" -f $resp.Content) -ForegroundColor Green
  } else {
    throw "Unexpected status: $($resp.StatusCode)"
  }
}
catch {
  $body = $_.Exception.Response | ForEach-Object { (New-Object IO.StreamReader($_.GetResponseStream())).ReadToEnd() }
  if ($body) { Write-Host ("Body: {0}" -f $body) -ForegroundColor DarkGray }
  Write-Host "Health check FAILED. Make sure your service is live and routes are under /api." -ForegroundColor Red
  Write-Host ("Tip: open in browser: {0}" -f $healthEP) -ForegroundColor Yellow
  exit 1
}

# [2..4] (optional) presign + upload + confirm would go here when you’re ready

# [5] Optional query (only works if /api/rag/query is exposed)
if ($DoQuery) {
  Write-Host "`n[5] Querying the index..." -ForegroundColor Cyan
  try {
    $q = @{ q = "what did the fox do?" }
    $resp = Invoke-WithRetry { Invoke-RestMethod -Uri $queryEP -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5) }
    Write-Host ("Query response: {0}" -f ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Green
  } catch {
    $code = $_.Exception.Response.StatusCode.value__ 2>$null
    Write-Host ("Query failed with HTTP {0}" -f $code) -ForegroundColor DarkYellow
    throw
  }
} else {
  Write-Host "[5] Query step skipped (user disabled)." -ForegroundColor DarkYellow
}

Write-Host "`nDone." -ForegroundColor Green







