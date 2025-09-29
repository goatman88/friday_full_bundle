# doctor.ps1 — run from repo root in **Windows PowerShell** (not pwsh)
param([switch]$Fix)
$ErrorActionPreference = "Stop"

function Note($m){ Write-Host $m -ForegroundColor Cyan }
function Good($m){ Write-Host "OK  $m" -ForegroundColor Green }
function Bad($m){ Write-Host "ERR $m" -ForegroundColor Red }

Push-Location $PSScriptRoot
Note "Repo root: $PWD"

# Tools
python --version | Out-Null;  if($LASTEXITCODE){ Bad "Python missing"; exit 1 } else { Good (python --version) }
node   -v       | Out-Null;  if($LASTEXITCODE){ Bad "Node missing";   exit 1 } else { Good (node -v) }
npm    -v       | Out-Null;  if($LASTEXITCODE){ Bad "npm missing";    exit 1 } else { Good (npm -v) }

# Files
$must = @(
  "backend\app.py",
  "backend\requirements.txt",
  "frontend\index.html",
  "frontend\src\main.js",
  "frontend\vite.config.js"
)
$missing = @($must | Where-Object { -not (Test-Path $_) })
if($missing.Count){
  Bad "Missing: $($missing -join ', ')"
  if(-not $Fix){ exit 1 }
}

# Backend import check (looks for backend.app:app)
$venvPy = ".\.venv\Scripts\python.exe"
$py = (Test-Path $venvPy) ? $venvPy : "python"
$code = "import importlib; m=importlib.import_module('backend.app'); print(hasattr(m,'app'))"
$ok = & $py -c $code
if("$ok" -ne "True"){ Bad "backend.app.app not found"; exit 1 } else { Good "backend exposes app" }

# Health endpoint (if backend is running)
try {
  $r = Invoke-WebRequest http://localhost:8000/api/health -UseBasicParsing -TimeoutSec 2
  if($r.StatusCode -eq 200){ Good "health endpoint reachable" } else { Bad "health HTTP $($r.StatusCode)" }
} catch { Note "Start backend then run doctor again for live check." }

# Frontend sanity
Push-Location frontend
if(-not (Test-Path package.json)){ Bad "frontend/package.json missing"; Pop-Location; exit 1 }
Good "frontend/package.json present"
Pop-Location

Good "Doctor complete"
Pop-Location
