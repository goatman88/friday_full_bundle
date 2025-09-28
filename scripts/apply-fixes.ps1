$ErrorActionPreference = "Stop"

# Write a Render start command suggestion
$render = @"
# If your Render service Working Directory is /backend:
uvicorn app:app --host 0.0.0.0 --port \$PORT

# If your Working Directory is repo root:
bash -lc 'cd backend && uvicorn app:app --host 0.0.0.0 --port \$PORT'
"@
Set-Content -Path (Join-Path (Split-Path $PSCommandPath -Parent) "render-start.txt") -Value $render -Encoding UTF8
Write-Host "✓ scripts/render-start.txt written (open this and copy the one that matches your Render Working Dir)"
