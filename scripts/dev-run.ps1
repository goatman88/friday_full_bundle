Param(
  [switch]$OpenBrowser
)

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass | Out-Null
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here

# 1) env (frees ports too)
& "$here\env.ps1"

# 2) start backend
Start-Process powershell -ArgumentList "-NoExit","-Command","`"$here\run-backend.ps1`""

# 3) start frontend
cd "$root\frontend"
npm install | Out-Null
Start-Process powershell -ArgumentList "-NoExit","-Command","npm run dev"

if ($OpenBrowser) {
  Start-Process "http://localhost:5173"
}




