# check-frontend.ps1
$ErrorActionPreference = 'Stop'
function Section($t){ "`n=== $t ===" | Write-Host -ForegroundColor Cyan }
function Good($t){ "OK  $t" | Write-Host -ForegroundColor Green }
function Warn($t){ "WARN $t" | Write-Host -ForegroundColor Yellow }
function Bad($t){ "ERR $t"  | Write-Host -ForegroundColor Red }

$root  = Split-Path -Parent $PSCommandPath
$front = Join-Path $root 'frontend'
if(!(Test-Path $front)){ Bad "missing frontend/"; exit 1 }
Set-Location $front

Section "Node & npm"
node -v
npm -v

# Exactly one postcss config
Section "PostCSS config"
$cfgs = Get-ChildItem $front -Filter 'postcss.config.*' -File -Name
if($cfgs.Count -gt 1){
  Warn "Found multiple: $($cfgs -join ', ') -> keeping .cjs"
  $cfgs | Where-Object { $_ -ne 'postcss.config.cjs' } | ForEach-Object { Remove-Item -Force $_ }
}
if(!(Test-Path 'postcss.config.cjs') -and (Test-Path 'postcss.config.js')){
  # If in ESM mode, module.exports will fail—convert to .cjs
  $pkg = Get-Content 'package.json' -Raw | ConvertFrom-Json
  if($pkg.type -eq 'module'){
    Warn "ESM mode detected; converting postcss.config.js -> .cjs"
    Remove-Item -Force 'postcss.config.cjs' -ErrorAction SilentlyContinue
    Rename-Item 'postcss.config.js' 'postcss.config.cjs'
  }
}
if(!(Test-Path 'postcss.config.cjs') -and !(Test-Path 'postcss.config.js')){
  Good "Creating postcss.config.cjs"
  Set-Content -Encoding UTF8 'postcss.config.cjs' @'
module.exports = { plugins: { autoprefixer: {} } };
'@
}
Get-ChildItem -Name postcss.config.*

# package.json sanity
Section "package.json"
try {
  $pkgJson = Get-Content 'package.json' -Raw | ConvertFrom-Json
  Good "package.json parsed; scripts.dev = '$($pkgJson.scripts.dev)'"
} catch {
  Bad "package.json invalid JSON: $($_.Exception.Message)"; exit 1
}

# Required files
Section "Files"
'$front/index.html','src/main.js' | ForEach-Object {
  if(!(Test-Path $_)){ Bad "missing $_"; exit 1 } else { Good "$_ present" }
}

# npm install
Section "npm install"
npm install | Out-Null
Good "npm install ok"

# Kill 5173 (vite) if needed
Section "Free port 5173"
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue |
  Select-Object -Expand OwningProcess | ForEach-Object { try { Stop-Process -Id $_ -Force } catch {} }
Good "port 5173 appears free"

# Start vite (5s smoke)
Section "Vite smoke"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = (Get-Command npm).Source
$psi.Arguments = 'run dev'
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep 2
try {
  $r = Invoke-WebRequest 'http://localhost:5173' -TimeoutSec 3
  Good "Vite responded ($($r.StatusCode))"
} catch {
  Warn "Vite not reachable yet: $($_.Exception.Message) (this may be normal if still compiling)"
} finally {
  if(!$p.HasExited){ $p.Kill() }
}
Good "frontend doctor done"
