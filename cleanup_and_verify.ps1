param(
  # Your backend Render URL (no trailing slash). Change this for your service.
  [string]$BackendUrl = "https://friday-099e.onrender.com",

  # Branch to push (Render is watching this one in your screenshots)
  [string]$Branch = "mtw27-client"
)

$ErrorActionPreference = 'Stop'

# --- 1) Locate the app.py we want to KEEP
$keepRel = "backend/app/app.py"

if (-not (Test-Path $keepRel)) {
  Write-Host "ERROR: $keepRel not found. Make sure the correct file exists." -ForegroundColor Red
  exit 1
}

$keepFull = (Resolve-Path $keepRel).Path

# --- 2) Find ALL app.py files (skip junk folders)
$all = Get-ChildItem -Recurse -Filter "app.py" -File `
  | Where-Object { $_.FullName -notmatch '\\\.git\\|\\node_modules\\|\\\.venv\\|\\dist\\|\\build\\' }

Write-Host "`n== Preview: ALL app.py files in repo ==" -ForegroundColor Cyan
$all | ForEach-Object {
  $p = $_.FullName
  if ($p -ieq $keepFull) {
    Write-Host ("KEEP   : {0}" -f $p) -ForegroundColor Green
  } else {
    Write-Host ("DELETE : {0}" -f $p) -ForegroundColor Yellow
  }
}

# --- 3) Confirm before deleting duplicates
$answer = Read-Host "`nContinue and delete all duplicates (leave ONLY $keepRel)? (y/N)"
if ($answer -notin @('y','Y','yes','YES')) {
  Write-Host "Aborted. Nothing deleted." -ForegroundColor Yellow
  exit 0
}

# --- 4) Delete duplicates
foreach ($f in $all) {
  if ($f.FullName -ieq $keepFull) { continue }
  try {
    Remove-Item -Force $f.FullName
    Write-Host ("Deleted {0}" -f $f.FullName) -ForegroundColor DarkYellow
  } catch {
    Write-Host ("Failed to delete {0}: {1}" -f $f.FullName, $_.Exception.Message) -ForegroundColor Red
  }
}

# --- 5) Verify only one remains
$remaining = Get-ChildItem -Recurse -Filter "app.py" -File `
  | Where-Object { $_.FullName -notmatch '\\\.git\\|\\node_modules\\|\\\.venv\\|\\dist\\|\\build\\' }

Write-Host "`n== Remaining app.py files ==" -ForegroundColor Cyan
$remaining | Select-Object -ExpandProperty FullName | ForEach-Object { Write-Host $_ }

if ($remaining.Count -ne 1 -or $remaining[0].FullName -ine $keepFull) {
  Write-Host "ERROR: Expected only $keepRel to remain." -ForegroundColor Red
  exit 1
}

# --- 6) Commit & push (PowerShell-safe; no bash operators)
git add -A
git commit -m "cleanup: keep only backend/app/app.py; remove duplicates" | Out-Null

# Bring branch up-to-date then push (handles 'non-fast-forward')
try {
  git fetch origin | Out-Null
  git pull --rebase origin $Branch
} catch {
  Write-Host "Pull (rebase) warning: $($_.Exception.Message)" -ForegroundColor Yellow
}
git push origin $Branch

# --- 7) Poll the health endpoints until they return 200 (or give up)
function Test-Url($url) {
  Write-Host ("`nChecking {0} ..." -f $url) -ForegroundColor Cyan
  $ok = $false
  for ($i = 1; $i -le 20; $i++) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -Method GET -TimeoutSec 10
      $ok = $true
      Write-Host ("OK {0} {1}" -f $r.StatusCode, $r.Content) -ForegroundColor Green
      break
    } catch {
      $code = $_.Exception.Response.StatusCode.value__
      $desc = $_.Exception.Response.StatusDescription
      Write-Host ("Attempt {0}: {1} {2}" -f $i, $code, $desc) -ForegroundColor Yellow
      Start-Sleep -Seconds 3
    }
  }
  if (-not $ok) {
    Write-Host ("Gave up on {0}" -f $url) -ForegroundColor Red
  }
  return $ok
}

$ok1 = Test-Url ("{0}/health" -f $BackendUrl)
$ok2 = Test-Url ("{0}/api/health" -f $BackendUrl)

if ($ok1 -and $ok2) {
  Write-Host "`nBoth health endpoints returned OK 🎉" -ForegroundColor Green
} else {
  Write-Host "`nStill failing. If Render logs show the app started, please paste the last 40 lines from the backend deploy logs." -ForegroundColor Magenta
}
