$ErrorActionPreference = "Stop"

function Ping($label,$url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url
    "{0}: {1} {2}" -f $label, $r.StatusCode, $r.Content
  } catch { "ERR {0}: {1}" -f $label, $_.Exception.Message }
}

Ping "health" "http://localhost:8000/api/health"

$body = @{ q = "ping" } | ConvertTo-Json
try {
  $r = Invoke-WebRequest "http://localhost:8000/api/ask" -Method Post -ContentType "application/json" -Body $body
  "ask: {0} {1}" -f $r.StatusCode,$r.Content
} catch { "ERR ask: {0}" -f $_.Exception.Message }
