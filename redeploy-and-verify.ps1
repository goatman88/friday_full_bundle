param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Site,
  [string]$FrontendPath = "$HOME/friday-frontend/frontend",
  [int]$MaxWaitSec = 180
)

function Say([string]$m,[string]$c=""){
  if($c){ Write-Host $m -ForegroundColor $c } else { Write-Host $m }
}
function Fail([string]$m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# -------- 1) Patch main.js (bake backend + absolute URLs) --------
$main = Join-Path $FrontendPath "src/main.js"
if(!(Test-Path $main)){ Fail "main.js not found at $main" }
$raw = Get-Content $main -Raw

# remove backslashes that broke Vite/Rollup before
$raw = $raw -replace "(?i)fetch\(\s*\\\\/api","fetch('/api"     # rare safety
$raw = $raw -replace "(?i)fetch\(\s*\\\\api","fetch('/api"      # rare safety
$raw = $raw -replace "(?i)fetch\(\s*/api","fetch('/api"         # normalize

# ensure a backend const at top (if none)
if($raw -notmatch "const\s+backend\s*="){
  $raw = "const backend = '$Backend';`r`n" + $raw
}else{
  $raw = $raw -replace "const\s+backend\s*=\s*['`"].*?['`"];","const backend = '$Backend';"
}

# convert relative fetch('/api/...') -> absolute `${backend}/api/...`
$raw = $raw -replace "(?i)fetch\(\s*['`"]\s*/api","fetch(`${backend}/api"

# prefer env if present in code (keep, but ensure absolute fallbacks)
$raw = $raw -replace "fetch\(\s*`?\$\{import\.meta\.env\.VITE_BACKEND_URL\}","fetch(`${import.meta.env.VITE_BACKEND_URL}`"

Set-Content $main -Value $raw -Encoding UTF8
Say "Patched src/main.js ✔" "Green"

# also write .env.local for Vite (Render Static reads at build time only)
$envLocal = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envLocal
Say "Updated .env.local" "Green"

# -------- 2) Clean build and verify locally --------
Push-Location $FrontendPath
try{
  if(Test-Path "node_modules"){ Remove-Item -Recurse -Force "node_modules" }
  if(Test-Path "dist"){ Remove-Item -Recurse -Force "dist" }
  if(Test-Path "package-lock.json"){ Remove-Item -Force "package-lock.json" }
  npm install | Out-Host
  npm run build | Out-Host
} catch { Fail "Local build failed: $($_.Exception.Message)" }
finally{ Pop-Location }

$assetsDir = Join-Path $FrontendPath "dist/assets"
if(!(Test-Path $assetsDir)){ Fail "Build output not found at $assetsDir" }
$bundle = Get-ChildItem $assetsDir -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if(!$bundle){ Fail "No built JS found under dist/assets" }
$js = Get-Content $bundle.FullName -Raw
$host = ([Uri]$Backend).Host
if($js -match [regex]::Escape($host)){
  Say "[PASS] Local bundle contains baked host: $host ($($bundle.Name))" "Green"
}else{
  Fail "Local bundle still missing baked host '$host'."
}

# -------- 3) Commit a tiny cache-busting change & push --------
$stamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
$versionFile = Join-Path $FrontendPath "src/.deploy-version.txt"
"deploy $stamp" | Out-File -Encoding UTF8 $versionFile
Push-Location $FrontendPath
git add "src/main.js" ".env.local" "src/.deploy-version.txt" | Out-Null
git commit -m "Frontend: bake backend host & cache-bust ($stamp)" | Out-Null
git push | Out-Host
Pop-Location

# -------- 4) Trigger Render deploy (if hook provided) --------
if($env:RENDER_DEPLOY_HOOK){
  Say "Triggering Render deploy via RENDER_DEPLOY_HOOK…" "Yellow"
  try{
    Invoke-WebRequest -Method POST -Uri $env:RENDER_DEPLOY_HOOK -TimeoutSec 20 | Out-Null
    Say "[PASS] Deploy hook called." "Green"
  }catch{
    Say "[WARN] Deploy hook call failed (continuing): $($_.Exception.Message)" "Yellow"
  }
}else{
  Say "[INFO] No RENDER_DEPLOY_HOOK in env. Relying on Git push to trigger build." "Yellow"
}

# -------- 5) Poll live site until new bundle shows baked host --------
$deadline = (Get-Date).AddSeconds($MaxWaitSec)
$seen = $false
$bundleUrl = $null

while((Get-Date) -lt $deadline -and -not $seen){
  try{
    $index = Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -Uri $Site
    $m = [regex]::Match($index.Content,'<script[^>]+type="module"[^>]*src="([^"]+\.js)"','IgnoreCase')
    if($m.Success){
      $p = $m.Groups[1].Value
      $bundleUrl = ($p -match '^https?://') ? $p : ($Site.TrimEnd('/') + '/' + $p.TrimStart('/'))
      $bundleLive = Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -Uri $bundleUrl
      if($bundleLive.Content -match [regex]::Escape($host)){
        $seen = $true
        break
      }
    }
  }catch{ Start-Sleep -Seconds 3 }
  Start-Sleep -Seconds 3
}

if($seen){
  Say "[PASS] Deployed bundle now includes backend host: $host" "Green"
  if($bundleUrl){ Say "Bundle: $bundleUrl" "DarkGray" }
  Say "All good ✅"
}else{
  Fail "Backend not found in deployed bundle after $MaxWaitSec sec. Clear build cache on Render (Static Site), then re-run."
}
