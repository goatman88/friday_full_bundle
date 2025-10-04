param(
  [Parameter(Mandatory=$true)][string]$Backend # e.g. https://friday-backend-ksep.onrender.com
)

$root = (Get-Location).Path
$fe   = Join-Path $root 'frontend'
$src  = Join-Path $fe   'src'

New-Item -ItemType Directory -Force -Path $src | Out-Null

# 1) env.mjs – single source of truth
$envPath = Join-Path $src 'env.mjs'
@"
export const BACKEND = (import.meta?.env?.VITE_BACKEND_URL || '$Backend').replace(/\/\$/, '');
"@ | Set-Content -Encoding UTF8 $envPath

# 2) main.js – simple UI + uses absolute BACKEND for all calls
$mainPath = Join-Path $src 'main.js'
@"
import { BACKEND } from './env.mjs';

async function ping() {
  const u = \`\${BACKEND}/api/health\`;
  const el = document.getElementById('out');
  try {
    const r = await fetch(u, { headers: { 'Content-Type': 'application/json' }});
    const t = await r.text();
    el.textContent = t;
  } catch (e) {
    el.textContent = 'Error: ' + (e?.message || e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.body.innerHTML = \`
    <h1>Friday Frontend</h1>
    <button id="btn">Ping backend</button>
    <pre id="out"></pre>
  \`;
  document.getElementById('btn').addEventListener('click', ping);
});
"@ | Set-Content -Encoding UTF8 $mainPath

# 3) index.html – load main.js as module
$indexPath = Join-Path $fe 'index.html'
@"
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Friday Frontend</title>
  </head>
  <body>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
"@ | Set-Content -Encoding UTF8 $indexPath

# 4) vite.config.js – dev proxy for local /api to real backend
$vitePath = Join-Path $fe 'vite.config.js'
@"
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: '$Backend',
        changeOrigin: true,
        secure: true
      }
    }
  }
});
"@ | Set-Content -Encoding UTF8 $vitePath

Write-Host "Wrote:"
Write-Host "  $envPath"
Write-Host "  $mainPath"
Write-Host "  $indexPath"
Write-Host "  $vitePath"
Write-Host ""
Write-Host "Next:"
Write-Host "  1) Commit & push these files"
Write-Host "  2) In Render Static Site -> Environment: keep ONLY 'VITE_BACKEND_URL = $Backend'"
Write-Host "  3) Manual Deploy -> Clear build cache & deploy"
