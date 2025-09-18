param(
    [string]$Base = "https://friday-099e.onrender.com/api",  # ✅ Include /api
    [switch]$DoQuery = $false
)

# Build endpoints
$healthEP  = "$Base/health"
$uploadEP  = "$Base/rag/upload_url"
$putEP     = "$Base/rag/upload_put/{token}"
$confirmEP = "$Base/rag/confirm_upload"
$queryEP   = "$Base/rag/query"

Write-Host "`n== Friday client ==" -ForegroundColor Cyan
Write-Host "Using base: $Base`n"
Write-Host "Endpoints:" -ForegroundColor Yellow
Write-Host "  health : $healthEP"
Write-Host "  upload : $uploadEP"
Write-Host "  put    : $putEP"
Write-Host "  confirm: $confirmEP"
Write-Host "  query  : $queryEP"







