param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

function Say($msg, [string]$color="") {
  if ($color) { Write-Host $msg -ForegroundColor $color } else { Write-Host $msg }
}
function Pass($msg) { Say "[PASS] $msg" "Green" }
function Fail($msg) { Say "[FAIL] $msg" "Red" }

Say "== Friday Frontend Auto Patch ==" "Cyan"
Say "Using backend: $Backend" "Yellow"

if (!(Test-Path $FrontendPath)) { Fail "Frontend folder not found at $FrontendPath"; exit 1 }

$envFile = Join-Path $FrontendPath ".env.local"
$viteCfg = Join-Path $FrontendPath "vite.config.js"

# 1) write .env.local for dev AND for bake step
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envFile
Pass "Updated .env.local"

# 2) ensure vite dev proxy points to backend (safe if file missing)
if (Test-Path $viteCfg) {
  $v = Get-Content $viteCfg -Raw
  if ($v -notmatch "server\s*:\s*{") {
    $v = @"
import { defineConfig } from 'vite'
export default defineConfig({
  server: { proxy: { '/api': { target: '$Backend', changeOrigin: true, secure: true } } }
})
"@
  } else {
    $v = $v -replace "target:\s*['""][^'""]+['""]", "target: '$Backend'"
    if ($v -notmatch "/api") {
      $v = $v -replace "server\s*:\s*{", "server:{ proxy:{ '/api':{ target:'$Backend', changeOrigin:true, secure:true } },"
    }
  }
  Set-Content -Encoding UTF8 $viteCfg $v
  Pass "Patched vite.config.js"
} else {
  Say "vite.config.js not found (ok for static-only usage)" "DarkGray"
}

# 3) make sure source fetch uses baked var (optional, keeps working in dev & prod)
$mainJs = Join-Path $FrontendPath "src/main.js"
if (Test-Path $mainJs) {
  $m = Get-Content $mainJs -Raw
  # fix backslashes that broke the build
  $m = $m -replace "\\\\\/api\/health","/api/health"
  # prefer using env var
  $m = $m -replace "fetch\(['""]\/api","fetch(`${import.meta.env.VITE_BACKEND_URL}/api"
  Set-Content -Encoding UTF8 $mainJs $m
  Pass "Patched src/main.js (env var + removed backslashes)"
}

# 4) build
Push-Location $FrontendPath
try {
  Say "Installing deps…"
  npm i | Out-Host
  Say "Building production bundle…"
  npm run build | Out-Host
  Pass "Local build completed. You can commit & push:"
  Say "  git add frontend/src/main.js frontend/.env.local frontend/vite.config.js" "DarkGray"
  Say "  git commit -m 'Frontend: bake backend & remove relative /api/*'" "DarkGray"
  Say "  git push" "DarkGray"
  Say "Then in Render (Static Site): Environment ➜ keep ONLY:  VITE_BACKEND_URL = $Backend" "Yellow"
  Say "Click **Manual Deploy** ➜ **Clear build cache & Deploy**." "Yellow"
}
catch {
  Fail ("Local build failed: {0}" -f $_.Exception.Message)
  exit 1
}
finally { Pop-Location }






