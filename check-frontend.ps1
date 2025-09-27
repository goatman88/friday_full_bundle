param(
  # Path to the repo root (parent of 'frontend'). Defaults to current dir.
  [string]$Root = (Get-Location).Path,
  # Try to auto-fix safe issues (remove stray postcss folder, create missing files)
  [switch]$Fix,
  # Also try to start Vite after checks pass
  [switch]$StartDev
)

$ErrorActionPreference = 'Stop'
function Section($t){Write-Host "`n=== $t ===" -ForegroundColor Cyan}
function Ok($t){Write-Host "OK  $t" -ForegroundColor Green}
function Warn($t){Write-Host "WARN $t" -ForegroundColor Yellow}
function Bad($t){Write-Host "ERR $t" -ForegroundColor Red}

$front = Join-Path $Root 'frontend'
$src   = Join-Path $front 'src'
$pkg   = Join-Path $front 'package.json'
$post  = Join-Path $front 'postcss.config.js'
$idx   = Join-Path $front 'index.html'
$main  = Join-Path $src   'main.js'

Section "Resolve paths"
Write-Host "Root: $Root"
Write-Host "Frontend: $front"
if(!(Test-Path $front)){ Bad "missing folder: $front"; if(-not $Fix){exit 1} else {New-Item -ItemType Directory -Force -Path $front | Out-Null; Ok "created $front"}}

# 1) Catch the exact Vite/PostCSS problem: accidental folder 'frontend\postcss\'
Section "PostCSS folder trap"
$badPostcssFolder = Join-Path $front 'postcss'
if(Test-Path $badPostcssFolder){
  Warn "Found folder '$($badPostcssFolder)'. This confuses Vite/PostCSS."
  if($Fix){
    Remove-Item -Recurse -Force $badPostcssFolder
    Ok "Removed stray folder: $badPostcssFolder"
  } else {
    Warn "Re-run with -Fix to remove it automatically."
  }
} else { Ok "No stray 'frontend\\postcss\\' folder" }

# 2) Ensure minimal files exist (index.html, postcss.config.js, src/main.js, package.json)
Section "Ensure minimal files exist"
if(!(Test-Path $src)){ if($Fix){ New-Item -ItemType Directory -Force -Path $src | Out-Null; Ok "created $src" } else { Bad "missing $src"; } }

if(!(Test-Path $idx) -and $Fix){
@'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Friday Frontend</title>
  </head>
  <body style="font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px;">
    <h1>Friday Frontend</h1>
    <section id="health" style="margin: 16px 0; padding: 12px; border: 1px solid #ddd;">
      <button id="btn-health">Check API /api/health</button>
      <pre id="health-out" style="white-space: pre-wrap; margin-top: 8px;"></pre>
    </section>
    <section id="ask" style="margin: 16px 0; padding: 12px; border: 1px solid #ddd;">
      <label for="q">Ask:</label>
      <input id="q" placeholder="type a question…" style="width: 60%; padding: 6px;" />
      <button id="btn-ask">Send</button>
      <pre id="ask-out" style="white-space: pre-wrap; margin-top: 8px;"></pre>
    </section>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
'@ | Set-Content -Encoding UTF8 $idx
  Ok "created $([IO.Path]::GetFileName($idx))"
}

if(!(Test-Path $main) -and $Fix){
@'
const API_BASE = "http://localhost:8000";
const el = (id) => document.getElementById(id);

el("btn-health").addEventListener("click", async () => {
  el("health-out").textContent = "…checking";
  try {
    const r = await fetch(`${API_BASE}/api/health`);
    const j = await r.json();
    el("health-out").textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    el("health-out").textContent = `Health error: ${e}`;
  }
});

el("btn-ask").addEventListener("click", async () => {
  const q = el("q").value.trim();
  if (!q) { el("ask-out").textContent = "Enter a question first."; return; }
  el("ask-out").textContent = "…sending";
  try {
    const r = await fetch(`${API_BASE}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q })
    });
    const j = await r.json();
    el("ask-out").textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    el("ask-out").textContent = `Ask error: ${e}`;
  }
});
'@ | Set-Content -Encoding UTF8 $main
  Ok "created src/main.js"
}

if(!(Test-Path $post) -and $Fix){
@'
module.exports = {
  plugins: { autoprefixer: {} }
};
'@ | Set-Content -Encoding UTF8 $post
  Ok "created postcss.config.js"
}

if(!(Test-Path $pkg) -and $Fix){
@'
{
  "name": "friday-frontend",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview --port 5173"
  },
  "devDependencies": {
    "vite": "^5.4.9",
    "postcss": "^8.4.47",
    "autoprefixer": "^10.4.20"
  }
}
'@ | Set-Content -Encoding UTF8 $pkg
  Ok "created package.json"
}

# 3) Validate file contents
Section "Validate files"
if(Test-Path $post){
  $txt = Get-Content $post -Raw
  if($txt.Trim().StartsWith('{')){ Bad "postcss.config.js is JSON – must be JS (module.exports = …)"; } else { Ok "postcss.config.js looks like JS" }
} else { Warn "postcss.config.js missing" }

if(Test-Path $pkg){
  try {
    $json = Get-Content $pkg -Raw | ConvertFrom-Json
    if($json.scripts.dev -ne 'vite'){ Warn "scripts.dev is '$($json.scripts.dev)'; expected 'vite'" } else { Ok "package.json parsed" }
  } catch {
    Bad "package.json not valid JSON: $($_.Exception.Message)"
  }
} else { Warn "package.json missing" }

if(Test-Path $idx){ Ok "index.html present" } else { Warn "index.html missing" }
if(Test-Path $main){ Ok "src/main.js present" } else { Warn "src/main.js missing" }

# 4) Node & npm sanity
Section "Node/npm"
try { $nodeV = node -v; Ok "node $nodeV" } catch { Bad "node not found"; exit 1 }
try { $npmV  = npm -v;  Ok "npm $npmV" }  catch { Bad "npm not found";  exit 1 }

# 5) Install deps if needed
Section "npm install"
Push-Location $front
try {
  if(Test-Path (Join-Path $front 'package-lock.json')){ npm ci | Out-Null } else { npm install | Out-Null }
  Ok "npm deps installed"
} catch { Bad "npm install failed: $($_.Exception.Message)" ; Pop-Location; exit 1 }

# 6) Backend quick health ping (optional)
Section "Backend /api/health"
try {
  $r = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 3
  Ok "backend responded: $($r.Content)"
} catch {
  Warn "backend not reachable on :8000 (start your uvicorn if you need it)"
}

# 7) Ensure dev port 5173 is free (optional clean if -Fix)
Section "Dev port 5173"
$port = 5173
$holders = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if($holders){
  Warn "something is already using :$port"
  if($Fix){
    $holders | Select-Object -Expand OwningProcess -Unique | ForEach-Object { Try { Stop-Process -Id $_ -Force -ErrorAction Stop } Catch {} }
    Ok "freed :$port"
  }
} else { Ok "port $port free" }

# 8) Optionally start Vite
if($StartDev){
  Section "Start Vite (CTRL+C to stop)"
  npm run dev
  Pop-Location
} else {
  Pop-Location
  Section "Done"
  Write-Host "Tip: start Vite with:  Push-Location `"$front`"; npm run dev" -ForegroundColor Gray
}
