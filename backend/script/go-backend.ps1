Param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
)
$backend = Join-Path $ProjectRoot "backend"
if (-not (Test-Path $backend)) {
  throw "Backend folder not found at: $backend"
}
Set-Location $backend
Write-Host "Now in: $(Get-Location)"
