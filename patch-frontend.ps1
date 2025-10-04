param(
    [Parameter(Mandatory = $true)][string]$Backend
)

Write-Host "🔧 Patching frontend bundle to point to backend: $Backend"

# Path to built frontend JS (adjust if needed)
$distPath = "frontend\dist"
$jsFile = Get-ChildItem $distPath -Filter "index-*.js" | Select-Object -First 1

if (-not $jsFile) {
    Write-Host "❌ No built JS file found in $distPath. Run 'npm run build' first."
    exit 1
}

$content = Get-Content $jsFile.FullName -Raw

# Replace any /api calls with the backend absolute URL
$content = $content -replace 'fetch\("/api', "fetch(`"$Backend/api"

Set-Content $jsFile.FullName $content -Encoding utf8

Write-Host "✅ Patched $($jsFile.Name) to use $Backend/api"

