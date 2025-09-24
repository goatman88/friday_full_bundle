Param(
  [string]$ApiBase = "http://localhost:8000",
  [switch]$Show
)

# (optional) set your OpenAI key here or in user env
# $env:OPENAI_API_KEY = "sk-...your-key..."

# handy for relative imports if you later make packages
$env:PYTHONPATH = (Resolve-Path "$PSScriptRoot\..").Path

# let frontend know where the backend is (vite can read these if you export upstream)
$env:VITE_BACKEND_BASE = $ApiBase

if ($Show) {
  Write-Host "Environment set:"
  Write-Host "  PYTHONPATH       = $($env:PYTHONPATH)"
  Write-Host "  VITE_BACKEND_BASE= $($env:VITE_BACKEND_BASE)"
}

