# doctor.ps1  (run from repo root)
$ErrorActionPreference = 'Stop'

function Note($msg, $color='Gray') { Write-Host $msg -ForegroundColor $color }
function Good($msg) { Note "OK  $msg" 'Green' }
function Bad($msg)  { Note "ERR $msg" 'Red' }

# 0) Where am I?
$root = Get-Location
Note "Repo root: $root" 'Cyan'

# 1) Tools
python --version | Out-Null; if ($LASTEXITCODE -ne 0) { Bad "Python not found"; exit 1 } else { python --version }
node -v | Out-Null; if ($LASTEXITCODE -ne 0) { Bad "Node not found"; exit 1 } else { node -v }
npm -v  | Out-Null; if ($LASTEXITCODE -ne 0) { Bad "npm not found";  exit 1 } else { npm -v  }

# 2) Files exist?
$must = @(
  "backend/app.py",
  "frontend/index.html",
  "frontend/src/main.js",
  "frontend/vite.config.js"
)
$missing = @()
foreach ($p in $must) { if (-not (Test-Path $p)) { $missing += $p } }
if ($missing.Count -gt 0) { $missing | % { Bad "Missing file: $_" }; exit 1 } else { Good "All required files present" }

# 3) backend.app exposes 'app'?
$cmd = "import importlib,sys;m=importlib.import_module('backend.app');sys.stdout.write(str(hasattr(m,'app')))"
$has = & python -c $cmd
if ($has -ne 'True') { Bad "backend.app does not expose 'app'"; exit 1 } else { Good "backend.app exposes 'app'" }

# 4) free ports 8000 and 5173
[int]$b=8000; [int]$f=5173
function Kill-Port([int]$p){
  Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
    Select-Object -Expand OwningProcess -Unique |
    ForEach-Object { try { Stop-Process -Id $_ -Force } catch {} }
}
Kill-Port $b; Kill-Port $f; Good "Ports $b and $f cleared"

# 5) Start backend
$backend = Start-Process pwsh -ArgumentList "-NoExit","-Command","cd '$root'; .\.venv\Scripts\Activate.ps1; uvicorn backend.app:app --host 0.0.0.0 --port $b --reload" -PassThru
Start-Sleep -Seconds 2

# 6) Start frontend
$frontend = Start-Process pwsh -ArgumentList "-NoExit","-Command","cd '$root\frontend'; npm install; npm run dev" -PassThru
Start-Sleep -Seconds 3

# 7) Probe health
try {
  $r = Invoke-WebRequest "http://localhost:$b/api/health" -UseBasicParsing -TimeoutSec 5
  if ($r.StatusCode -eq 200 -and $r.Content -match '"ok"') { Good "Backend health OK" } else { Bad "Backend health unexpected: $($r.StatusCode)" }
} catch { Bad "Backend not reachable on $b: $_" }

Note "Open:" 'Yellow'
Note "  http://localhost:$f/" 'Yellow'
Note "  http://localhost:$b/api/health" 'Yellow'
