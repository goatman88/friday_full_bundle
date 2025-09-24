Param(
  [string]$ApiBase = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

# Show where we are
Write-Host "🔧 Environment" -ForegroundColor Cyan
Write-Host "Backend :" $ApiBase -ForegroundColor DarkCyan
$env:API_BASE = $ApiBase

# Optional convenient defaults for models/voice
if (-not $env:TEXT_MODEL)      { $env:TEXT_MODEL      = "gpt-4o-mini" }
if (-not $env:REALTIME_MODEL)  { $env:REALTIME_MODEL  = "gpt-4o-realtime-preview-2024-12-17" }
if (-not $env:REALTIME_VOICE)  { $env:REALTIME_VOICE  = "verse" }

Write-Host "TEXT_MODEL     =" $env:TEXT_MODEL
Write-Host "REALTIME_MODEL =" $env:REALTIME_MODEL
Write-Host "REALTIME_VOICE =" $env:REALTIME_VOICE

Write-Host "✅ Environment set." -ForegroundColor Green
