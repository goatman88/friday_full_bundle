@echo off
REM Requires curl.exe (Windows 10+ already has it)

if "%FRIDAY_BASE%"=="" (
  echo Set FRIDAY_BASE first & exit /b 1
)
if "%API_TOKEN%"=="" (
  echo Set API_TOKEN first & exit /b 1
)

curl -s ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Accept: application/json" ^
  %FRIDAY_BASE%/__routes

pause
