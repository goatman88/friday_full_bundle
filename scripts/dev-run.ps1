param([switch]$OpenBrowser)

$ErrorActionPreference = "Stop"
$root = (Get-Location)
$backend = Join-Path $root "backend"
$front   = Join-Path $root "friday-frontend"
if (-not (Test-Path $front)) { $front = $root }  # your project folder is sometimes named friday-frontend/friday-frontend

# Free ports 8000/5173 (best-effort)
foreach ($p in 8000,5173) {
  Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

# Install backend deps
Push-Location $backend
python -m pip install -r requirements.txt | Out-Null
# Start uvicorn
$be = Start-Process pwsh -PassThru -ArgumentList @(
  "-NoLogo","-NoProfile","-NoExit",
  "-Command","Set-Location `"$backend`"; python -m uvicorn app:app --host 0.0.0.0 --port 8000"
)
Pop-Location

# Install frontend deps if package.json exists
$frontPkg = Join-Path $front "package.json"
if (Test-Path $frontPkg) {
  Push-Location $front
  npm install | Out-Null
  $fe = Start-Process pwsh -PassThru -ArgumentList @(
    "-NoLogo","-NoProfile","-NoExit",
    "-Command","Set-Location `"$front`"; npm run dev"
  )
  Pop-Location
}

Write-Host "Dev servers launching.  Backend : http://localhost:8000  |  Frontend : http://localhost:5173"
if ($OpenBrowser) { Start-Process "http://localhost:5173" }
