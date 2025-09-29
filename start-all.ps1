# start-all.ps1
$ErrorActionPreference = "Stop"
Start-Process powershell -WorkingDirectory $PWD -ArgumentList "-NoExit","-Command",".\.venv\Scripts\Activate.ps1; uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"
Start-Sleep -Seconds 1
Start-Process powershell -WorkingDirectory "$PWD\frontend" -ArgumentList "-NoExit","-Command","npm run dev"
