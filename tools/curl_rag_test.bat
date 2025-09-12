@echo off
REM Usage (all quotes required around params that contain spaces):
REM   set FRIDAY_BASE=https://friday-099e.onrender.com
REM   set API_TOKEN=mvtest_7hj3w8k2
REM   tools\curl_rag_test.bat "Widget FAQ" "Widgets are blue and waterproof." "faq" "What color are widgets?" 5 showctx

setlocal

if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"==""   echo Set API_TOKEN first & exit /b 1

set "TITLE=%~1"
set "TEXT=%~2"
set "SOURCE=%~3"
set "QUERY=%~4"
set "TOPK=%~5"
if "%TOPK%"=="" set TOPK=3
set "SHOW=%~6"

echo --- 1) Indexing note ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"%TITLE%\",\"text\":\"%TEXT%\",\"source\":\"%SOURCE%\"}"
echo.
echo -------------------------

echo.
echo --- 2) Querying note ---
if /I "%SHOW%"=="showctx" (
  curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
    -H "Authorization: Bearer %API_TOKEN%" ^
    -H "Content-Type: application/json" ^
    -d "{\"question\":\"%QUERY%\",\"top_k\":%TOPK%,\"show_contexts\":true}"
) else (
  curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
    -H "Authorization: Bearer %API_TOKEN%" ^
    -H "Content-Type: application/json" ^
    -d "{\"question\":\"%QUERY%\",\"top_k\":%TOPK%}"
)
echo.



