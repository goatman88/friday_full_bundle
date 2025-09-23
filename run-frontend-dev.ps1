param()

$ErrorActionPreference = "Stop"
Write-Host ">>> Starting FRONTEND on port 5173..." -ForegroundColor Cyan

# Ensure Node is available
$node = (Get-Command node -ErrorAction SilentlyContinue)
if (-not $node) { throw "Node.js not found on PATH. Install Node/NVM for Windows and reopen terminal." }

# Use npm.cmd to avoid the npm.ps1 shim bug
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $npm) { throw "npm.cmd not found. Verify Node/NPM installation." }

# Install once if needed
if (-not (Test-Path node_modules)) {
  Write-Host "Installing frontend deps..." -ForegroundColor Yellow
  & $npm ci 2>$null; if ($LASTEXITCODE -ne 0) { & $npm install }
}

# Run dev
& $npm run dev



