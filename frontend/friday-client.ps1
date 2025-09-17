# friday-client.ps1
# Full end-to-end client for Friday RAG API

# ========== CONFIG ==========
$domain    = "https://friday-099e.onrender.com"
$uploadUrl = "$domain/api/rag/upload_url"
$confirmUrl= "$domain/api/rag/confirm_upload"
$queryUrl  = "$domain/api/rag/query"
$healthUrl = "$domain/api/health"

Write-Host "`n>>> Checking health..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri $healthUrl -Method GET
$health | Format-List

# ========== STEP 1: Request presigned URL ==========
Write-Host "`n>>> Requesting presigned upload URL..." -ForegroundColor Cyan
$presignReq = @{
  filename     = "demo.txt"
  content_type = "text/plain"
}
$presign = Invoke-RestMethod -Uri $uploadUrl -Method POST `
  -ContentType "application/json" `
  -Body ($presignReq | ConvertTo-Json -Depth 5)
$presign | Format-List

$putUrl = $presign.put_url
$s3Uri  = $presign.s3_uri

# ========== STEP 2: Upload file to S3 ==========
Write-Host "`n>>> Uploading demo content to S3..." -ForegroundColor Cyan
$bytes = [System.Text.Encoding]::UTF8.GetBytes("Hello from Friday client via PowerShell")
Invoke-WebRequest -Uri $putUrl -Method PUT -Body $bytes -ContentType "text/plain"
Write-Host "Upload complete." -ForegroundColor Green

# ========== STEP 3: Confirm / index ==========
Write-Host "`n>>> Confirming upload..." -ForegroundColor Cyan
$confirmReq = @{
  s3_uri     = $s3Uri
  title      = "demo_file"
  external_id= "demo_1"
  metadata   = @{ collection="default"; tags=@("test"); source="cli" }
  chunk      = @{ size=1200; overlap=150 }
}
$confirm = Invoke-RestMethod -Uri $confirmUrl -Method POST `
  -ContentType "application/json" `
  -Body ($confirmReq | ConvertTo-Json -Depth 6)
$confirm | Format-List

# ========== STEP 4: Query ==========
Write-Host "`n>>> Querying the index..." -ForegroundColor Cyan
$q = @{ q = "what did the fox do?" }
$response = Invoke-RestMethod -Uri $queryUrl -Method POST `
  -ContentType "application/json" `
  -Body ($q | ConvertTo-Json -Depth 5)
$response | Format-List
