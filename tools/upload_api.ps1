param(
  [string]$FilePath = "$env:USERPROFILE\Downloads\sample.pdf"
)

if (-not $env:FRIDAY_BASE) { throw "Set `$env:FRIDAY_BASE" }
if (-not $env:API_TOKEN)   { throw "Set `$env:API_TOKEN" }
if (-not (Test-Path $FilePath)) { throw "File not found: $FilePath" }

# 1) build multipart
Add-Type -AssemblyName System.Net.Http
$client = [System.Net.Http.HttpClient]::new()
$client.DefaultRequestHeaders.Authorization = `
  New-Object System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", $env:API_TOKEN)

$fs = [System.IO.File]::OpenRead($FilePath)
$sc = New-Object System.Net.Http.StreamContent($fs)
$sc.Headers.ContentType = New-Object System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream")

$mp = New-Object System.Net.Http.MultipartFormDataContent
# name the part "file" and include filename
$null = $mp.Add($sc, "file", (Split-Path $FilePath -Leaf))
# optional notes
$null = $mp.Add([System.Net.Http.StringContent]::new("testing upload from ps"), "notes")

# 2) POST
$resp = $client.PostAsync("$($env:FRIDAY_BASE)/data/upload", $mp).Result
$status = [int]$resp.StatusCode
$body   = $resp.Content.ReadAsStringAsync().Result
Write-Host "Status: $status"
Write-Host "Body:   $body"

# dispose
$mp.Dispose(); $fs.Dispose(); $client.Dispose()
