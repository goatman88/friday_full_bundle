<#  ------------------------------------------------------------
    deploy.ps1
    - Writes a correct render.yaml for your monorepo
    - Commits & pushes changes to the current branch
    - Prints verification URLs/commands

    Usage examples:
      ./deploy.ps1
      ./deploy.ps1 -BackendApiBase "https://friday-099e.onrender.com/api"
      ./deploy.ps1 -CommitMessage "Adjust render blueprint"
  ------------------------------------------------------------ #>

param(
  [string]$BackendApiBase = "https://friday-099e.onrender.com/api",
  [string]$CommitMessage  = "Update render.yaml (backend rootDir+start, frontend rootDir+build+dist)"
)

function Fail($msg) { Write-Host "`nERROR: $msg" -ForegroundColor Red; exit 1 }

# ---- 0) Quick repo sanity checks ----
if (-not (Test-Path -Path ".git")) { Fail "Run this from the Git repo root." }
if (-not (Test-Path -Path "backend/app/app.py")) { Fail "Expected backend/app/app.py but it wasn't found." }
if (-not (Test-Path -Path "backend/requirements.txt")) { Fail "Expected backend/requirements.txt but it wasn't found." }
if (-not (Test-Path -Path "friday-frontend/package.json")) { Fail "Expected friday-frontend/package.json but it wasn't found." }

# ---- 1) Write render.yaml ----
$yaml = @"
services:
  - type: web
    name: friday
    env: python
    rootDir: backend
    plan: free
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt
    startCommand: uvicorn app.app:app --host 0.0.0.0 --port \$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11

  - type: static
    name: friday_full_bundle
    rootDir: friday-frontend
    buildCommand: npm ci && npm run build
    staticPublishPath: dist
    envVars:
      - key: VITE_API_BASE
        value: $BackendApiBase
"@

Set-Content -Encoding UTF8 -Path "render.yaml" -Value $yaml
Write-Host "`n✔ Wrote render.yaml with VITE_API_BASE = $BackendApiBase" -ForegroundColor Green

# ---- 2) Git: add/commit, rebase-pull if needed, push ----
# Stage only the files we changed/need
git add render.yaml | Out-Null

# If nothing to commit, continue; else commit
$changes = (git status --porcelain)
if ($changes) {
  git commit -m $CommitMessage | Out-Null
  Write-Host "✔ Git commit created." -ForegroundColor Green
} else {
  Write-Host "ℹ No local file changes detected (render.yaml may already match)." -ForegroundColor Yellow
}

# Try push. If rejected, do a rebase-pull and push again.
$push = git push 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "⚠ Push rejected; attempting 'git pull --rebase'..." -ForegroundColor Yellow
  git pull --rebase || Fail "git pull --rebase failed; resolve conflicts and re-run."
  git push        || Fail "git push failed after rebase; check your remote/branch."
  Write-Host "✔ Push succeeded after rebase." -ForegroundColor Green
} else {
  Write-Host "✔ Push succeeded." -ForegroundColor Green
}

# ---- 3) Helpful verification output ----
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1) Backend service (Render) should be configured as:"
Write-Host "   - Root Directory: backend"
Write-Host "   - Start Command : uvicorn app.app:app --host 0.0.0.0 --port \$PORT"
Write-Host "   (render.yaml now documents this for you.)"
Write-Host ""
Write-Host "2) Static site (Render) should be configured as:"
Write-Host "   - Root Directory   : friday-frontend"
Write-Host "   - Build Command    : npm ci && npm run build"
Write-Host "   - Publish Directory: dist"
Write-Host "   (also documented in render.yaml)."
Write-Host ""
Write-Host "3) In Render, on both services: click 'Clear build cache' then 'Deploy' (backend first, then frontend)."
Write-Host ""
Write-Host "4) Quick checks:" -ForegroundColor Cyan
Write-Host "   Backend Health:  Invoke-WebRequest -UseBasicParsing `"$BackendApiBase/health`" | Select-Object -ExpandProperty Content"
Write-Host "   (Expected: {`"status`":`"ok`"})"
Write-Host ""
Write-Host "   Frontend: open your static site URL. It should show 'API: <Render URL>/api — Health: OK'."
Write-Host ""
Write-Host "Done ✅"
