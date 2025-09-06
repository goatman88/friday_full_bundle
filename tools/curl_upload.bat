@echo off
REM set once per machine/VM (edit these 2 lines)
set "FRIDAY_BASE=https://friday-099e.onrender.com"
set "API_TOKEN=PUT_YOUR_TOKEN_HERE"

REM pick a file to send (edit if you want a different file)
set "FILE=%USERPROFILE%\Downloads\sample.pdf"

if not exist "%FILE%" (
  echo File not found: %FILE%
  pause
  exit /b 1
)

echo Uploading...
curl.exe -s -X POST "%FRIDAY_BASE%/data/upload" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -F "file=@%FILE%" ^
  -F "notes=testing upload"

echo.
echo Asking chat to summarize...
curl.exe -s -X POST "%FRIDAY_BASE%/chat" ^
  -H "Authorization: Bearer %API_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Summarize the PDF I just uploaded.\"}"
echo.
pause
