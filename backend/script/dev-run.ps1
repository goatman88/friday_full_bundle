Param(
  [int]$Port = 8000,
  [switch]$OpenBrowser
)

# 0) run from this script's directory so relative paths work
Set-Location (Resolve-Path "$PSScriptRoot\..")

# 1) activate venv if you have one next to backend folder (optional)
if (Test-Path "..\.venv\Scripts\Activate.ps1") {
  & "..\.venv\Scripts\Activate.ps1"
}

# 2) free the port if it's stuck
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
  ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }

# 3) start uvicorn
Write-Host "Starting backend on http://localhost:$Port ..."
$proc = Start-Process -PassThru powershell -ArgumentList @(
  "-NoLogo","-NoProfile","-Command",
  "uvicorn app:app --host 0.0.0.0 --port $Port --reload"
)

# 4) open docs (helpful)
if ($OpenBrowser) {
  Start-Sleep -Seconds 1
  Start-Process "http://localhost:$Port/docs"
}

