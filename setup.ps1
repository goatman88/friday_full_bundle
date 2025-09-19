<#  setup.ps1
    Helper for pushing changes to GitHub and (optionally) writing render.yaml

    Example:
      ./setup.ps1 -Message "Deploy: lock PostCSS + add render.yaml" -WriteRenderYaml `
                  -BackendUrl "https://friday-backend.onrender.com/api" -Branch "mtw27-client"
#>

param(
  [Parameter(Mandatory=$false)][string]$Message = "chore: deploy",
  [Parameter(Mandatory=$false)][string]$Branch  = "mtw27-client",
  [Parameter(Mandatory=$false)][string]$BackendUrl = "https://friday-backend.onrender.com/api",
  [switch]$WriteRenderYaml
)

# --- helpers ---------------------------------------------------------------
function Fail($msg) { Write-Host "`nERROR: $msg" -ForegroundColor Red; exit 1 }
function Ok($msg)   { Write-Host $msg -ForegroundColor Green }

# --- sanity checks ---------------------------------------------------------
if (-not (Test-Path ".git")) { Fail "Run this from the repo root (no .git folder found)." }
if (-not (Test-Path "backend")) { Fail "backend/ folder not found in this directory." }
if (-not (Test-Path "friday-frontend")) { Fail "friday-frontend/ folder not found in this directory." }

Write-Host "Repo root looks good." -ForegroundColor Cyan

# --- optionally write/overwrite render.yaml --------------------------------
if ($WriteRenderYaml) {
  $yaml = @"
services:
  - type: web
    name: friday-backend
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.app:app --host 0.0.0.0 --port 10000

  - type: web
    name: friday-frontend
    env: node
    rootDir: friday-frontend
    buildCommand: |
      npm install
      npm run build
    staticPublishPath: dist
    envVars:
      - key: VITE_API_BASE
        value: $BackendUrl
"@

  Set-Content -Encoding utf8 -Path "render.yaml" -Value $yaml
  Ok "Wrote render.yaml with VITE_API_BASE = $BackendUrl"
}

# --- show a tiny status before we stage ------------------------------------
Write-Host "`nGit status (short):"
git status -s

# --- stage changes (respecting .gitignore) ---------------------------------
Write-Host "`nStaging changes..." -ForegroundColor Cyan
git add -A

# --- if nothing to commit, continue to pull/push anyway --------------------
$pending = (git diff --cached --name-only)
if ([string]::IsNullOrWhiteSpace($pending)) {
  Write-Host "Nothing to commit; continuing to pull --rebase / push."
} else {
  git commit -m $Message | Out-Null
  Ok "Committed: $Message"
}

# --- keep branch in sync ---------------------------------------------------
Write-Host "`nRebasing on origin/$Branch ..." -ForegroundColor Cyan
git pull origin $Branch --rebase || Fail "git pull --rebase failed. Resolve conflicts and re-run."

Write-Host "Pushing to origin/$Branch ..." -ForegroundColor Cyan
git push origin $Branch || Fail "git push failed."

Ok "`nDone! Your changes are on GitHub."
Write-Host @"
Next steps:
  1) Render will pick up your repo changes on the next deploy.
  2) If you created the services using render.yaml, you can trigger a Manual Deploy
     on both services from the Render dashboard (Backend + Frontend).
"@
