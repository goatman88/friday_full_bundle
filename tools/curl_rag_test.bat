@echo off
REM Requires curl.exe (Windows 10+ has it built-in)

if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"=="" echo Set API_TOKEN first & exit /b 1

echo ============================
echo Indexing note...
curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Acme Note\",\"text\":\"Acme builds rockets and coffee machines.\",\"source\":\"manual\"}"
echo.

echo ============================
echo Querying...
curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"What does Acme build?\"}"
echo.
pause

