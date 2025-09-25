$ErrorActionPreference = "Stop"
. "$PSScriptRoot\env.ps1"

$backend = Start-Process powershell -PassThru -NoNewWindow -ArgumentList @(
  "-NoExit","-Command","cd '$PSScriptRoot\..\backend'; uvicorn app:app --host 0.0.0.0 --port 8000 --reload"
)
$frontend = Start-Process powershell -PassThru -NoNewWindow -ArgumentList @(
  "-NoExit","-Command","cd '$PSScriptRoot\..\frontend'; npm install; npm run dev"
)

Write-Host "Backend PID: $($backend.Id)  Frontend PID: $($frontend.Id)"
Start-Process "http://localhost:5173"




