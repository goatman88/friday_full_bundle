# run-frontend-dev.ps1
$ErrorActionPreference = "Stop"
cd $PSScriptRoot
if (-not (Test-Path "node_modules")) { npm ci }
# If you want to point dev at local backend, keep VITE_API_BASE empty (proxy handles it).
# If you want to point dev at Render, set it here:
# $env:VITE_API_BASE = "https://friday-099e.onrender.com"
npm run dev
