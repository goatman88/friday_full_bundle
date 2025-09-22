# Start backend, frontend, and voice loop in three windows
Start-Process powershell -ArgumentList '-NoExit','-Command', '.\run-backend-dev.ps1'
Start-Process cmd        -ArgumentList '/k','npm run dev'
Start-Process powershell -ArgumentList '-NoExit','-Command', 'setx PICOVOICE_ACCESS_KEY "<PUT_YOUR_KEY_HERE>"; .\.venv\Scripts\Activate.ps1; python backend\voice_loop.py'
