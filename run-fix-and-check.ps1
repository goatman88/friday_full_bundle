param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Site
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $here "fix-step1.ps1") -Backend $Backend
& (Join-Path $here "doctor-frontend.ps1") -Backend $Backend -Site $Site
