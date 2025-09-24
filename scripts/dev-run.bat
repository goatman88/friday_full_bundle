@echo off
setlocal ENABLEDELAYEDEXPANSION

REM - Resolve paths
set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..

REM - Load env
call "%SCRIPT_DIR%env.bat"

REM - Optional: free ports 5173 and 8000 (best-effort; ignored if nothing to kill)
for %%P in (5173 8000) do (
  powershell -NoProfile -Command ^
    "Get-NetTCPConnection -LocalPort %%P -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} }" >nul 2>&1
)

REM - Start BACKEND (PowerShell so we can activate venv)
start "Backend" powershell -NoExit -Command ^
  "cd '%REPO_ROOT%'; ^ 
   if (Test-Path '.venv/Scripts/Activate.ps1') { . '.venv/Scripts/Activate.ps1' } else { Write-Host 'WARN: venv not found' -ForegroundColor Yellow }; ^
   uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"

REM - Start FRONTEND (plain cmd so npm loads faster)
start "Frontend" cmd /K ^
  "cd /d ""%REPO_ROOT%\frontend"" && npm run dev"

REM - Open browser if "-OpenBrowser" arg passed
if /I "%~1"=="-OpenBrowser" start "" http://localhost:5173

echo.
echo [dev-run.bat] Launched:
echo   - Backend on http://localhost:8000
echo   - Frontend on http://localhost:5173
echo   (close these two terminals to stop)
echo.
endlocal
