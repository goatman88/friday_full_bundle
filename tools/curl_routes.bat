@echo off
REM Quick routes probe (requires API_TOKEN)
REM Usage:
REM   set FRIDAY_BASE=https://your-app.onrender.com
REM   set API_TOKEN=your_token
REM   tools\curl_routes.bat

if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"==""   echo Set API_TOKEN first   & exit /b 1

curl -s "%FRIDAY_BASE%/__routes" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Accept: application/json"
echo.



