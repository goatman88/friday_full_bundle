# Quick health + ask checks against local backend
$iwrArgs = @{ UseBasicParsing = $true }

Write-Host "GET /health:" -ForegroundColor Cyan
iwr http://localhost:8000/health @iwrArgs | Select-Object -ExpandProperty StatusCode

Write-Host "GET /api/health:" -ForegroundColor Cyan
iwr http://localhost:8000/api/health @iwrArgs | Select-Object -ExpandProperty StatusCode

$body = @{ q = "ping" } | ConvertTo-Json
Write-Host "POST /api/ask:" -ForegroundColor Cyan
iwr http://localhost:8000/api/ask -Method Post -ContentType "application/json" -Body $body |
  Select-Object -ExpandProperty Content

Write-Host "POST /api/session:" -ForegroundColor Cyan
iwr http://localhost:8000/api/session -Method Post -ContentType "application/json" -Body "{}" |
  Select-Object -ExpandProperty Content


