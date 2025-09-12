@echo off
REM Usage:
REM   set FRIDAY_BASE=https://your-app.onrender.com
REM   set API_TOKEN=your_token
REM   tools\curl_rag_test.bat "Title" "Text" "source" "Question" [TopK]

setlocal
if "%FRIDAY_BASE%"=="" echo Set FRIDAY_BASE first & exit /b 1
if "%API_TOKEN%"==""   echo Set API_TOKEN first   & exit /b 1

set "TITLE=%~1"
set "TEXT=%~2"
set "SOURCE=%~3"
set "QUERY=%~4"
set "TOPK=%~5"

if "%TITLE%"==""  set "TITLE=Acme Note"
if "%TEXT%"==""   set "TEXT=Acme builds rockets and coffee machines."
if "%SOURCE%"=="" set "SOURCE=manual"
if "%QUERY%"==""  set "QUERY=What does Acme build?"
if "%TOPK%"==""   set "TOPK=2"

echo.
echo --- 1) Indexing note ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"%TITLE%\",\"text\":\"%TEXT%\",\"source\":\"%SOURCE%\"}"

echo.
echo.
echo --- 2) Querying note ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"%QUERY%\",\"top_k\":%TOPK%}"
echo.
endlocal




