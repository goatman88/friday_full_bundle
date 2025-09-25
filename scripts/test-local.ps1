Param([string]$ApiBase = "http://localhost:8000")

Write-Host "GET $ApiBase/health" -ForegroundColor Yellow
try { (iwr "$ApiBase/health").StatusCode } catch { $_.Exception.Message }

Write-Host "GET $ApiBase/api/health" -ForegroundColor Yellow
try { (iwr "$ApiBase/api/health").StatusCode } catch { $_.Exception.Message }

Write-Host "POST $ApiBase/api/ask" -ForegroundColor Yellow
$body = @{ q = "what did the fox do?" } | ConvertTo-Json
try { iwr "$ApiBase/api/ask" -Method Post -ContentType "application/json" -Body $body } catch { $_.Exception.Message }

