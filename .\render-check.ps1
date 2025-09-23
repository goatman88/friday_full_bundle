<# 
render-check.ps1
Verifies your Render URLs and your server import string locally.
Usage:
  pwsh -f .\render-check.ps1 -Backend "https://your-backend.onrender.com" -Frontend "https://your-frontend.onrender.com" -Import "backend.app:app"
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Frontend,
  [string]$Import = "backend.app:app"
)

$ErrorActionPreference = "Stop"

function Check([string]$name,[scriptblock]$b){
  try{ & $b; Write-Host "✓ $name" -ForegroundColor Green }
  catch{ Write-Host "✗ $name" -ForegroundColor Red; throw }
}

# 1) URL shape (must start with https://)
Check "Backend URL shape" { if(!$Backend.StartsWith("https://")){ throw "Backend must start with https://"} }
Check "Frontend URL shape" { if(!$Frontend.StartsWith("https://")){ throw "Frontend must start with https://"} }

# 2) Deployed healths
Check "GET $Backend/health"     { (iwr "$Backend/health").StatusCode -eq 200 | Out-Null }
Check "GET $Backend/api/health" { (iwr "$Backend/api/health").StatusCode -eq 200 | Out-Null }

# 3) Ask roundtrip
$body = @{ prompt = "Hello from render-check"; latency="fast" } | ConvertTo-Json
Check "POST $Backend/api/ask" { irm "$Backend/api/ask" -Method Post -ContentType "application/json" -Body $body | Out-Null }

# 4) Local import path matches files (prevents 'app not found' on Render)
$parts = $Import.Split(":")
if($parts.Count -ne 2){ throw "Import must be 'package.module:attr', e.g. backend.app:app" }
$mod = $parts[0]; $attr = $parts[1]
$py = Join-Path (Get-Location) (($mod -replace "\.", "\") + ".py")
if(!(Test-Path $py)){ 
  Write-Host "⚠ The file $py does not exist locally. If your app is in backend\main.py, set -Import 'backend.main:app'." -ForegroundColor Yellow
}else{
  $hasApp = Select-String -Path $py -Pattern "app\s*=\s*FastAPI" -SimpleMatch
  if(!$hasApp){ Write-Host "⚠ $py exists but no 'app = FastAPI(...)' found. Ensure your FastAPI instance is named 'app'." -ForegroundColor Yellow }
}

Write-Host "`nAll checks that could be run have completed." -ForegroundColor Cyan
