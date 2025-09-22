$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
# try Porcupine; if it fails, we still run in hotkey mode
pip install pvporcupine pvrecorder 2>$null

Write-Host ">> Starting voice / wake-word on ws://localhost:8765 ..." -ForegroundColor Cyan
python backend/voice_loop.py
