@echo off
REM Friday RAG quick test (Windows CMD + curl)
REM Save as: tools\curl_rag_test.bat
REM Usage:
REM   1) set FRIDAY_BASE=https://<your-render>.onrender.com
REM   2) set API_TOKEN=<your token>
REM   3) tools\curl_rag_test.bat
REM Optional overrides:
REM   tools\curl_rag_test.bat "Widget FAQ" "Widgets are blue and waterproof." "faq" "What color are widgets?" 5 SHOW

setlocal ENABLEDELAYEDEXPANSION

REM ---- guard rails ----
if "%FRIDAY_BASE%"=="" (
  echo [x] FRIDAY_BASE is not set. Example:
  echo     set FRIDAY_BASE=https://friday-xxxx.onrender.com
  exit /b 1
)
if "%API_TOKEN%"=="" (
  echo [x] API_TOKEN is not set. Example:
  echo     set API_TOKEN=mvtest_abc123
  exit /b 1
)

REM ---- defaults (can be overridden by args) ----
set TITLE=Acme Note
set TEXT=Acme builds rockets and coffee machines.
set SOURCE=manual
set QUERY=What does Acme build?
set TOPK=3
set SHOWCTX=

if not "%~1"=="" set "TITLE=%~1"
if not "%~2"=="" set "TEXT=%~2"
if not "%~3"=="" set "SOURCE=%~3"
if not "%~4"=="" set "QUERY=%~4"
if not "%~5"=="" set "TOPK=%~5"
if /I "%~6"=="SHOW" set SHOWCTX=1

echo.
echo --- 1) Indexing note ---
echo Title: %TITLE%
echo Source: %SOURCE%

curl -s -X POST "%FRIDAY_BASE%/api/rag/index" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"%TITLE%\",\"text\":\"%TEXT%\",\"source\":\"%SOURCE%\"}"

echo.
echo --------------------------

echo.
echo --- 2) Querying (%TOPK% results) ---
curl -s -X POST "%FRIDAY_BASE%/api/rag/query" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"%QUERY%\",\"top_k\":%TOPK%%(SHOWCTX%)%}"

goto :eof

:SHOWCTX
REM helper to inject show_contexts when requested
REM (this label is called via variable expansion below)
:eof

