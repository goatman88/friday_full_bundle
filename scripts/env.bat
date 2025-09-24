@echo off
REM ——— Environment for local dev ———
set VITE_API_BASE=http://localhost:8000
set VITE_SESSION_ID=local-dev

echo.
echo [env.bat] Environment set:
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:5173
echo   VITE_API_BASE=%VITE_API_BASE%
echo.
