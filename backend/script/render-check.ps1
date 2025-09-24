Param(
  [Parameter(Mandatory=$true)][string]$Backend,
  [Parameter(Mandatory=$true)][string]$Frontend
)

function Show($label,$uri) {
  try {
    $r = Invoke-WebRequest -Uri $uri -UseBasicParsing
    "{0}: {1} {2}" -f $label,$r.StatusCode,$uri
  } catch {
    "ERROR -> {0}: {1}" -f $label,$_.Exception.Message
  }
}

Show "Backend /health" "$Backend/health"
Show "Backend /api/health" "$Backend/api/health"
Show "Frontend" $Frontend
