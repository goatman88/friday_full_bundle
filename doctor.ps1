<# Friday doctor – run from repo root to diagnose quickly #>
$ErrorActionPreference = 'Continue'

function Ok($t){  Write-Host "OK  $t" -ForegroundColor Green }
function Bad($t){ Write-Host "ERR $t" -ForegroundColor Red }
function Info($t){ Write-Host $t -ForegroundColor Cyan }

Info "== Versions =="
python --version
if ($LASTEXITCODE -ne 0) { Bad "Python missing" } else { Ok "Python found" }
node -v
npm -v
if ($LASTEXITCODE -ne 0) { Bad "Node/npm missing" } else { Ok "Node & npm found" }

Info "== File checks =="
if (Test-Path backend/app.py) { Ok "backend/app.py exists" } else { Bad "missing backend/app.py" }
if (Test-Path backend/requirements.txt) { Ok "backend/requirements.txt exists" } else { Bad "missing backend/requirements.txt" }
if (Test-Path frontend/package.json) { Ok "frontend/package.json exists" } else { Bad "missing frontend/package.json" }

Info "== FastAPI 'app' export =="
$py = Get-Command python | Select-Object -Expand Source
$code = "import importlib,sys; m=importlib.import_module('backend.app'); sys.stdout.write('1' if hasattr(m,'app') else '0')"
$has = & $py -c $code
if ($has -eq '1') { Ok "backend.app exposes 'app'" } else { Bad "backend.app DOES NOT expose 'app'" }

Info "== Ports =="
foreach ($p in 8000,5173){
  $busy = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
  if ($busy) { Bad "port $p busy" } else { Ok "port $p free" }
}

