param (
  [Parameter(Mandatory=$true)][string]$Backend = "https://friday-backend-ksep.onrender.com",
  [string]$FrontendPath = "$PSScriptRoot/frontend"
)

Write-Host "=== Friday Frontend Auto Patch ===" -ForegroundColor Cyan
Write-Host "Using backend: $Backend" -ForegroundColor Yellow

# 1️⃣ Ensure frontend folder exists
if (!(Test-Path $FrontendPath)) {
  Write-Host "❌ Frontend folder not found at $FrontendPath" -ForegroundColor Red
  exit 1
}

# 2️⃣ Create .env.local with backend URL
$envFile = Join-Path $FrontendPath ".env.local"
"VITE_BACKEND_URL=$Backend" | Out-File -Encoding UTF8 $envFile
Write-Host "✅ Created .env.local with backend URL" -ForegroundColor Green

# 3️⃣ Patch vite.config.js if proxy missing
$vitePath = Join-Path $FrontendPath "vite.config.js"
if (Test-Path $vitePath) {
  $vite = Get-Content $vitePath -Raw
  if ($vite -notmatch "proxy") {
    $proxyBlock = @"
server: {
  proxy: {
    '/api': {
      target: '$Backend',
      changeOrigin: true,
      secure: true
    }
  }
},
"@
    $vite = $proxyBlock + "`n" + $vite
    Set-Content -Encoding UTF8 $vitePath $vite
    Write-Host "✅ Patched vite.config.js to include proxy" -ForegroundColor Green
  } else {
    Write-Host "ℹ️ vite.config.js already includes proxy" -ForegroundColor Yellow
  }
} else {
  Write-Host "❌ vite.config.js not found in frontend/" -ForegroundColor Red
}

# 4️⃣ Run npm install + build
Push-Location $FrontendPath
try {
  Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
  npm install | Out-Host
  Write-Host "🏗️ Building production bundle..." -ForegroundColor Cyan
  npm run build | Out-Host
  Write-Host "✅ Build complete" -ForegroundColor Green
} catch {
  Write-Host "❌ Build failed: $($_.Exception.Message)" -ForegroundColor Red
}
Pop-Location

# 5️⃣ Verify if backend URL is baked
$distIndex = Get-ChildItem -Recurse $FrontendPath -Filter "index.html" | Select-Object -First 1
if ($distIndex) {
  $content = Get-Content $distIndex.FullName -Raw
  if ($content -match [regex]::Escape($Backend)) {
    Write-Host "✅ SUCCESS: Backend URL is baked into the build!" -ForegroundColor Green
  } else {
    Write-Host "❌ FAIL: Backend not baked. Clear cache & redeploy on Render manually." -ForegroundColor Red
  }
} else {
  Write-Host "⚠️ No index.html found to verify build output." -ForegroundColor Yellow
}

Write-Host "=== Done ===" -ForegroundColor Cyan
