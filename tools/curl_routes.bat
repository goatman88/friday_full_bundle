@echo off
REM Requires curl.exe (built into Windows 10+)

IF "%FRIDAY_BASE%"==""  echo Set FRIDAY_BASE first & exit /b 1
IF "%API_TOKEN%"==""    echo Set API_TOKEN first & exit /b 1

curl -s ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Accept: application/json" ^
  "%FRIDAY_BASE%/__routes"

echo.
pause

