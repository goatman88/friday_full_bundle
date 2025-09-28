# scripts\go-backend.ps1
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $here "..")
Set-Location (Join-Path $root "backend")
pwd
