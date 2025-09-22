# open-repo.ps1
$repo = "C:\Users\mtw27\friday-frontend\friday-frontend"
if (-not (Test-Path $repo)) { Write-Host "Repo path missing: $repo" -ForegroundColor Red; exit 1 }
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd `"$repo`"; git rev-parse --abbrev-ref HEAD; ls"
