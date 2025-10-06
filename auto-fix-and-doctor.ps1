param(
  [Parameter(Mandatory=$true )][string]$Backend,         # e.g. https://friday-backend-ksep.onrender.com
  [Parameter(Mandatory=$true )][string]$FrontendPath,    # e.g. $HOME/friday-frontend/frontend
  [string]$Site    = "",                                 # optional deployed static site URL
  [string]$DeployHook = "",                              # optional Render deploy hook URL
  [int]$WaitMin = 10                                     # poll minutes after deploy hook
)

$ErrorActionPreference = "Stop"

function Ok   ([string]$m){ Write-Host "[PASS] $m" -ForegroundColor Green }
function Warn ([string]$m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail ([string]$m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# Helpers
$backendHost = ([Uri]$Backend).Host
function Esc([string]$s){ [regex]::Escape($s) }

Write-Host "=== Friday: Auto Fix + Build + Doctor ===" -ForegroundColor Cyan
Write-Host ("Backend : {0}" -f $Backend)       -ForegroundColor Yellow
Write-Host ("Frontend: {0}" -f $FrontendPath)  -ForegroundColor Yellow
if($Site){ Write-Host ("Static  : {0}" -f $Site) -ForegroundColor Yellow }

# -------- 0) Paths
$srcDir = Join-Path $FrontendPath "src"
$main  = Join-Path $srcDir "main.js"
if(!(Test-Path $main)){ Fail ("main.js not found at {0}" -f $main) }

# -------- 1) Patch src/main.js
# Normalize any existing const backend; otherwise inject it.
# Also normalize any accidental backslashes and rewrite relative fetch('/api/...') to baked host.
$raw = Get-Content $main -Raw

# remove accidental Windows backslashes in fetchs
$raw = $raw -replace "(?i)fetch\((['""])\s*\\?/api","fetch($1$Backend/api"

# Ensure a const backend at the top (inject if missing)
if($raw -notmatch "(?m)^\s*const\s+backend\s*="){
  $raw = "const backend = `"$Backend`";`r`n" + $raw
}else{
  # normalize existing const backend to new value
  $raw = $raw -replace "(?m)^\s*const\s+backend\s*=\s*(['""]).*?\1\s*;","const backend = `"$Backend`";"
}

# Force any remaining relative '/api' calls to use baked host
$raw = $raw -replace "(?i)fetch\((['""])\s*/api","fetch($1$Backend/api"

Set-Content -Encoding UTF8 -Path $main -Value $raw
Ok "Patched src/main.js"

# -------- 2) Clean-ish build
Push-Location $FrontendPath
try{
  if(Test-Path (Join-Path $FrontendPath "dist")){ Remove-Item -Recurse -Force (Join-Path $FrontendPath "dist") }
  if(Test-Path (Join-Path $FrontendPath "node_modules")){ Remove-Item -Recurse -Force (Join-Path $FrontendPath "node_modules") }
  if(Test-Path (Join-Path $FrontendPath "package-lock.json")){ Remove-Item -Force (Join-Path $FrontendPath "package-lock.json") }

  npm install | Out-Host
  Write-Host "Building production bundle..." -ForegroundColor DarkGray
  npm run build | Out-Host
  Ok "Local build completed."
}catch{
  Fail ("Local build failed: {0}" -f $_.Exception.Message)
}finally{ Pop-Location }

# -------- 3) Verify local bundle (baked host + no '/api/*')
$assetsDir = Join-Path $FrontendPath "dist/assets"
if(!(Test-Path $assetsDir)){ Fail ("Build output not found at {0}" -f $assetsDir) }

$bundle = Get-ChildItem $assetsDir -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if(!$bundle){ Fail "No built JS found under dist/assets" }

$js = Get-Content $bundle.FullName -Raw
$hasHost = $js -match (Esc $backendHost)
$hasRel  = $js -match "fetch\((\s*['""])\s*/api"

if($hasHost -and -not $hasRel){
  Ok ("Baked OK: found host {0} in {1}" -f $backendHost,$bundle.Name)
}else{
  if(-not $hasHost){ Warn ("Local bundle DOES NOT include backend host (baked absolute URL).") }
  if($hasRel){       Warn ("Local bundle still contains relative '/api/*' calls.") }
  Warn  "Local bundle needs fix (missing host and/or relative '/api')."
  exit 2
}

# -------- 4) (optional) Verify deployed static site
function Verify-Deployed([string]$siteUrl){
  try{
    $index = Invoke-WebRequest -Uri $siteUrl -UseBasicParsing -TimeoutSec 30
    $m = [regex]::Match($index.Content,'<script[^>]+type="module"[^>]+src="([^"]+\.js)"','IgnoreCase')
    if(-not $m.Success){ Fail "Could not find module <script> in deployed index.html" }

    $jsPath = $m.Groups[1].Value
    # build absolute URL for module
    $bundleUrl = if($jsPath -match '^https?://'){ $jsPath } else { ($siteUrl.TrimEnd('/') + '/' + $jsPath.TrimStart('/')) }
    Ok ("Found deployed bundle: {0}" -f $bundleUrl)

    $remote = Invoke-WebRequest -Uri $bundleUrl -UseBasicParsing -TimeoutSec 30
    $hasHostDeployed = $remote.Content -match (Esc $backendHost)
    $hasRelDeployed  = $remote.Content -match "fetch\((\s*['""])\s*/api"

    if($hasHostDeployed -and -not $hasRelDeployed){
      Ok "Deployed bundle references backend host and uses absolute URLs."
      return 0
    }else{
      if(-not $hasHostDeployed){
        Warn ("Result: Deployed bundle does NOT include the backend host. Keep ONLY this env in Render (Static Site): VITE_BACKEND_URL = {0}" -f $Backend)
      }
      if($hasRelDeployed){
        Warn "Result: Deployed bundle still contains relative '/api/*' calls."
        Warn "Hint: Ensure code uses baked const or env, e.g. fetch(backend + '/api/...') or fetch(`${import.meta.env.VITE_BACKEND_URL}/api/...`)."
      }
      return 2
    }
  }catch{
    Fail ("Fetch deployed bundle failed: {0}" -f $_.Exception.Message)
  }
}

$exitCode = 0
if($Site){
  $exitCode = Verify-Deployed -siteUrl $Site

  # ----- 5) (optional) trigger deploy hook + poll
  if($DeployHook -and $Site){
    try{
      Invoke-WebRequest -Method POST -Uri $DeployHook -TimeoutSec 20 | Out-Null
      Ok "Triggered Render deploy hook."
    }catch{
      Warn ("Deploy hook call failed: {0}" -f $_.Exception.Message)
    }

    $deadline = (Get-Date).AddMinutes($WaitMin)
    do{
      Start-Sleep -Seconds 10
      try{
        $exitCode = Verify-Deployed -siteUrl $Site
        if($LASTEXITCODE -eq 0 -or $exitCode -eq 0){ Ok "Deployed bundle looks good."; break }
      }catch{}
    }while((Get-Date) -lt $deadline)

    if($exitCode -ne 0){
      Fail ("Backend not found in deployed bundle after {0} min. Clear Static Site build cache in Render UI and redeploy." -f $WaitMin)
    }
  }
}

exit $exitCode
