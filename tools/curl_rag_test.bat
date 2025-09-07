@echo off
REM tools/curl_rag_test.bat
REM Requires Windows 10+ (curl.exe is built-in). Run from Command Prompt (not PowerShell).

IF "%FRIDAY_BASE%"=="" (
  echo Set FRIDAY_BASE first, e.g.
  echo   set FRIDAY_BASE=https://friday-o99e.onrender.com
  pause
  exit /b 1
)
IF "%API_TOKEN%"=="" (
  echo Set API_TOKEN first, e.g.
  echo   set API_TOKEN=mvtest_7hj3w8k2
  pause
  exit /b 1
)

echo Using:
echo   FRIDAY_BASE=%FRIDAY_BASE%
echo   API_TOKEN=(hidden)
echo.

REM --- 1) index a note ---
echo Indexing note...
curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Acme Note\",\"text\":\"Acme builds rockets and coffee machines.\",\"source\":\"manual\"}"
echo.
echo ----------------------------

REM --- 2) query it ---
echo Querying...
curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"What does Acme build?\"}"
echo.
echo ----------------------------

pause
