$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location $root
git add backend frontend render.yaml scripts
git commit -m "apply fixes: backend app, vite proxy, render.yaml, helper scripts" 2>$null
git push origin main
Write-Host "📤 Pushed to origin/main. Render should redeploy now." -ForegroundColor Green
