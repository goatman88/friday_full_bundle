@echo off
REM curl_rag_test.bat
REM Usage: curl_rag_test.bat "TITLE" "TEXT" "SOURCE" "QUERY"

if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"=="" echo Set API_TOKEN first & exit /b 1

set TITLE=%~1
set TEXT=%~2
set SOURCE=%~3
set QUERY=%~4

echo.
echo --- 1) Indexing note ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"%TITLE%\",\"text\":\"%TEXT%\",\"source\":\"%SOURCE%\"}"

echo.
echo --- 2) Querying note ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"%QUERY%\"}"


