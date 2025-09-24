Param([string]$Base="http://localhost:8000")

function Show($label,$uri) {
  try {
    $r = Invoke-WebRequest -Uri $uri
    "{0}: {1}" -f $label,$r.StatusCode
    $r.Content
  } catch { "ERROR {0}: {1}" -f $label,$_.Exception.Message }
}

Show "root /health" "$Base/health"
Show "api  /health" "$Base/api/health"

$body = @{ q="ping" } | ConvertTo-Json
$r = Invoke-WebRequest -Uri "$Base/api/ask" -Method Post -ContentType "application/json" -Body $body
"ask -> " + $r.Content

$r2 = Invoke-WebRequest -Uri "$Base/api/session" -Method Post
"session -> " + $r2.Content

