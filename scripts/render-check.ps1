Param(
  [Parameter(Mandatory)][string]$Backend,
  [Parameter(Mandatory)][string]$Frontend
)

function Show($label,$uri){
  try {
    $r = iwr -Uri $uri -UseBasicParsing
    "{0}: {1}" -f $label,$r.StatusCode
  } catch {
    "{0}: ERROR -> {1}" -f $label,$_.Exception.Message
  }
}

Show "Backend /health" "$Backend/health"
Show "Backend /api/health" "$Backend/api/health"
Show "Frontend" $Frontend


