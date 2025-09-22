$ErrorActionPreference = 'Stop'
$repo = "C:\Users\mtw27\friday-frontend\friday-frontend"
if (-not (Test-Path $repo)) { throw "Repo path not found: $repo" }

Set-Location $repo
Write-Host "Repo root: $(Get-Location)" -ForegroundColor Green

# quick port sanity
function Test-Port($port){ (Test-NetConnection 127.0.0.1 -Port $port).TcpTestSucceeded }
if (Test-Port 8000) { Write-Host "Warning: port 8000 already in use." -ForegroundColor Yellow }
if (Test-Port 5173) { Write-Host "Warning: port 5173 already in use." -ForegroundColor Yellow }

# Try Windows Terminal panes
$wt = (Get-Command wt.exe -ErrorAction SilentlyContinue)
if ($wt) {
  # Left pane: backend
  $cmdBackend  = "powershell -NoExit -Command `"cd `"$repo`"; ./run-backend-dev.ps1`""
  # Right pane: frontend
  $cmdFrontend = "powershell -NoExit -Command `"cd `"$repo`"; ./run-frontend-dev.ps1`""

  & wt.exe new-tab $cmdBackend `
      ; split-pane -H $cmdFrontend `
      ; focus-tab -t 1 | Out-Null

} else {
  # Fallback: two separate windows
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd `"$repo`"; ./run-backend-dev.ps1"
  Start-Sleep 2
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd `"$repo`"; ./run-frontend-dev.ps1"
}

# Auto-open browser **after** vite becomes reachable
$viteUrl = "http://localhost:5173"
for ($i=0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $viteUrl -TimeoutSec 2
    if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { 
      Start-Process $viteUrl
      break
    }
  } catch { Start-Sleep -Milliseconds 500 }
}
