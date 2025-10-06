param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

function Say($msg, [string]$color=""){
  if ($color -eq "Green") { Write-Host $msg -ForegroundColor Green }
  elseif ($color -eq "Yellow") { Write-Host $msg -ForegroundColor Yellow }
  elseif ($color -eq "Red") { Write-Host $msg -ForegroundColor Red }
  else { Write-Host $msg }
}

function Fail($msg){
  Say "[FAIL] $msg" "Red"
  exit 1
}

Say "=== Friday: Fix + Bake + Verify ===" "Cyan"
Say "Backend  : $Backend" "Yellow"
Say "Frontend : $FrontendPath" "Yellow"

# Step 1: Fix main.js
$main = Join-Path $FrontendPath "src/main.js"
if (!(Test-Path $main)) { Fail "main.js not found at $main" }

$raw = Get-Content $main -Raw
$raw = $raw -replace "(?i)fetch\(['""]\/api", "fetch(`"$Backend/api"
$raw = $raw -replace "(?i)const backend\s*=.*", "const backend = `"$Backend`";"
Set-Content $main -Value $raw -Encoding UTF8
Say "Patched src/main.js ✅" "Green"

# Step 2: Build clean
Push-Location $FrontendPath
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "node_modules") { Remove-Item -Recurse -Force "node_modules" }
npm install | Out-Host
npm run build | Out-Host
Pop-Location

# Step 3: Verify baked result
$assetsDir = Join-Path $FrontendPath "dist/assets"
if (!(Test-Path $assetsDir)) { Fail "Build output not found at $assetsDir" }

$bundle = Get-ChildItem $assetsDir -Filter *.js | Sort-Object Length -Descending | Select-Object -First 1
if (!$bundle) { Fail "No built JS found under dist/assets" }

$content = Get-Content $bundle.FullName -Raw
if ($content -match [regex]::Escape($Backend)) {
  Say "[PASS] Backend successfully baked into bundle ✅" "Green"
} else {
  Fail "Backend NOT baked! Check your Render env or fetch path."
}

Say "=== Done! ===" "Cyan"
