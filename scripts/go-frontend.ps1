$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
Set-Location "$root\frontend"
# If vite isn’t installed yet, install dependencies once:
if (-not (Test-Path "node_modules")) { if (Test-Path "package-lock.json") { npm ci } else { npm i } }
# If 5173 is busy, Vite will auto-prompt to use a new port; allow it.
npm run dev
