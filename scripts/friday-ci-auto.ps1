<#
.SYNOPSIS
  Friday CI/CD automation pipeline — full version.
  Builds frontend, checks backend, optionally triggers Render deploys, and validates everything end-to-end.
#>

param(
  [Parameter(Mandatory=$true)][string]$FrontendDir,
  [Parameter(Mandatory=$true)][string]$DeployedSite,
  [Parameter(Mandatory=$true)][string]$BackendUrl,

  [switch]$DoLocalBuild,
  [switch]$DoRenderDeploys,

  [string]$RenderApiKey     = $env:RENDER_API_KEY,
  [string]$BackendServiceId = $env:BACKEND_SERVICE_ID,
  [string]$FrontendServiceId= $env:FRONTEND_SERVICE_ID
)

$ErrorActionPreference = "Stop"

function Write-Head([string]$text) { Write-Host "`n== $text ==" -ForegroundColor Cyan }

# --------------- Helpers ---------------
function Try-Get($url) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20
    Write-Host "[PASS] $url -> $($r.StatusCode) $($r.Content)" -ForegroundColor Green
  } catch {
    Write-Host "[WARN] $url -> $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

function Quick-Backend-Smoke([string]$Base) {
  Write-Head "Backend smoke"
  Try-Get "$Base/api/health"
  Try-Get "$Base/api/time"
  Try-Get "$Base/api/version"
}

function Check-Deployed-Frontend([string]$Site, [string]$Backend) {
  Write-Head "Frontend bundle check (deployed)"
  try {
    $idx = Invoke-WebRequest -Uri $Site -UseBasicParsing -TimeoutSec 30
    $m = [regex]::Match($idx.Content, '<script[^>]+type="module"[^>]+src="([^"]+\.js)"', 'IgnoreCase')
    if (-not $m.Success) { throw "No module script found in index.html" }

    $bundleUrl = if ($m.Groups[1].Value -match '^https?://') {
      $m.Groups[1].Value
    } else {
      "$($Site.TrimEnd('/'))/$($m.Groups[1].Value.TrimStart('/'))"
    }

    $js = (Invoke-WebRequest -Uri $bundleUrl -UseBasicParsing -TimeoutSec 30).Content
    $hostNoScheme = ($Backend -replace '^https?://', '')
    $hasHost = $js -match ([regex]::Escape($hostNoScheme))
    $hasRel  = $js -match 'fetch\(\s*["'']\/api'

    if ($hasHost -and -not $hasRel) {
      Write-Host "[PASS] Deployed bundle uses backend host and has no relative /api calls." -ForegroundColor Green
    } elseif (-not $hasHost) {
      Write-Host "[WARN] Deployed bundle missing backend host. Check Render env: VITE_BACKEND_URL = $Backend" -ForegroundColor Yellow
    } elseif ($hasRel) {
      Write-Host "[WARN] Deployed bundle still has relative /api calls – replace with import.meta.env.VITE_BACKEND_URL." -ForegroundColor Yellow
    }
  } catch {
    Write-Host "[FAIL] Frontend smoke failed: $($_.Exception.Message)" -ForegroundColor Red
  }
}

function Build-Frontend-Local([string]$Dir, [string]$Backend) {
  Write-Head "Local frontend build (bake host)"
  if (Test-Path $Dir) {
    Push-Location $Dir
    try {
      if (-not (Test-Path ".\node_modules")) {
        npm ci | Out-Null
      }
      $env:VITE_BACKEND_URL = $Backend
      npx vite build
    } catch {
      Write-Warning "[WARN] Local vite build failed: $($_.Exception.Message)"
    } finally { Pop-Location }
  } else {
    Write-Warning "[WARN] FrontendDir not found: $Dir"
  }
}

function Deploy-And-Wait([string]$ServiceId, [string]$Label) {
  if ([string]::IsNullOrWhiteSpace($ServiceId)) { return }
  Write-Head "Triggering Render deploy for $Label"
  $headers = @{ Authorization = "Bearer $RenderApiKey"; "Content-Type" = "application/json" }
  $body = @{ clearCache = $true; message = "Friday auto-deploy" } | ConvertTo-Json
  $url = "https://api.render.com/v1/services/$ServiceId/deploys"
  $deploy = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
  $deployId = $deploy.id

  do {
    Start-Sleep -Seconds 6
    $d = Invoke-RestMethod -Uri "https://api.render.com/v1/deploys/$deployId" -Headers $headers
    Write-Host "  [$Label] status: $($d.status)" -ForegroundColor DarkGray
  } while ($d.status -in @("build_in_progress","update_in_progress","queued"))

  if ($d.status -eq "live") {
    Write-Host "✅ $Label is live." -ForegroundColor Green
  } else {
    Write-Warning "$Label deploy ended in status: $($d.status)"
  }
}

# --------------- PIPELINE ---------------
Write-Head "Friday CI/CD starting"

if ($DoLocalBuild) { Build-Frontend-Local -Dir $FrontendDir -Backend $BackendUrl }

$canDeploy = $DoRenderDeploys -and $RenderApiKey -and $BackendServiceId -and $FrontendServiceId
if ($canDeploy) {
  try {
    Deploy-And-Wait -ServiceId $BackendServiceId  -Label "backend"
    Deploy-And-Wait -ServiceId $FrontendServiceId -Label "frontend"
  } catch {
    Write-Warning "[WARN] Render deploy failed: $($_.Exception.Message)"
  }
} else {
  Write-Head "Render deploys skipped"
  Write-Host "Set envs or pass params to enable: RENDER_API_KEY, BACKEND_SERVICE_ID, FRONTEND_SERVICE_ID" -ForegroundColor Yellow
}

Quick-Backend-Smoke -Base $BackendUrl
Check-Deployed-Frontend -Site $DeployedSite -Backend $BackendUrl

Write-Host "`n✅ Friday CI/CD pipeline complete!" -ForegroundColor Cyan
