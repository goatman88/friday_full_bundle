# friday-client.ps1
# Full end-to-end test client for Friday RAG API

$ErrorActionPreference = "Stop"

# -------------------------------
# CONFIG
# -------------------------------
$domain    = "https://friday-099e.onrender.com"
$ragBase   = "$domain/api/rag"
$healthUrl = "$domain/api/health"

# Test file to upload
$testFilePath = "demo.txt"
Set-Content -Path $testFilePath -Value "Hello from Friday PowerShell client!" -Encoding UTF8

# -------------------------------
# 1) Health Check
# -------------------------------
Write-Host "`n[1] Health check..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri $healthUrl -Method GET
Write-Host "Health:" ($health | ConvertTo-Json -Depth 3) -ForegroundColor Green

# -------------------------------
# 2) Upload (Presigned URL)
# -------------------------------
Write-Host "`n[2] Upload request..." -ForegroundColor Cyan
$presignReq = @{
    filename    = "demo.txt"
    contentType = "text/plain"
}
$presign = Invoke-RestMethod -Uri "$ragBase/upload_url" -Method POST -ContentType "application/json" -Body ($presignReq | ConvertTo-Json -Depth 3)

$putUrl = $presign.put_url
$s3Uri  = $presign.s3_uri

Write-Host "PUT to S3: $s3Uri" -ForegroundColor Yellow
Invoke-WebRequest -Uri $putUrl -Method PUT -InFile $testFilePath -ContentType "text/plain"
Write-Host "Upload complete." -ForegroundColor Green

# -------------------------------
# 3) Confirm Upload / Index
# -------------------------------
Write-Host "`n[3] Confirm upload..." -ForegroundColor Cyan
$confirmReq = @{
    s3_uri      = $s3Uri
    title       = "demo_file"
    external_id = "demo_1"
    metadata    = @{ collection = "default"; tags = @("test"); source = "cli" }
    chunk       = @{ size = 1200; overlap = 150 }
}
$confirmUrl = "$ragBase/confirm_upload"
$confirm = Invoke-RestMethod -Uri $confirmUrl -Method POST -ContentType "application/json" -Body ($confirmReq | ConvertTo-Json -Depth 6)
Write-Host "Confirm response:" ($confirm | ConvertTo-Json -Depth 3) -ForegroundColor Green

# -------------------------------
# 4) Query
# -------------------------------
Write-Host "`n[4] Query index..." -ForegroundColor Cyan
$queryUrl = "$ragBase/query"
$q = @{ q = "What did the fox do?" }

try {
    $resp = Invoke-RestMethod -Uri $queryUrl -Method POST -ContentType "application/json" -Body ($q | ConvertTo-Json -Depth 5)
    Write-Host "Query response:" ($resp | ConvertTo-Json -Depth 3) -ForegroundColor Green
}
catch {
    Write-Host "Query failed with $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nDone ✅" -ForegroundColor Green

