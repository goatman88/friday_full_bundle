# commits & pushes so Render redeploys (assumes 'origin' points to GitHub)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path); Set-Location ..
git add backend frontend render.yaml scripts
git commit -m "apply fixes: backend app, vite proxy, render.yaml, helper scripts" 2>$null
git push origin main
Write-Host "📤 Pushed to origin/main. Render should redeploy automatically." -ForegroundColor Green
