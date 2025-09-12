@echo off
REM Usage:
REM   set FRIDAY_BASE=https://friday-099e.onrender.com
REM   set API_TOKEN=mvtest_7hj3w8k2
REM   tools\curl_routes.bat

if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"==""   echo Set API_TOKEN first & exit /b 1

curl -s "%FRIDAY_BASE%/__routes" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Accept: application/json"
echo.


