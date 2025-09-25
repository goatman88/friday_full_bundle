param(
  [switch]$Recreate
)

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root

# Ensure folders
$dirs = @('backend','frontend','frontend\src','scripts')
foreach ($d in $dirs) { if (-not (Test-Path $d)) { New-Item -Type Directory $d | Out-Null } }

# --- Backend files ---
$backendApp = @'
import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Friday Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173","*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

class AskIn(BaseModel):
    q: str

@app.post("/api/ask")
def ask(payload: AskIn):
    q = payload.q.strip()
    if not q:
        return {"answer": "(empty question)"}
    return {"answer": f"You asked: {q}"}

@app.post("/api/session")
def session():
    return {"id":"local-session","models":{"voice":"none","text":"none"}}
'@

$backendReq = @'
fastapi==0.116.2
uvicorn[standard]==0.30.6
pydantic==2.9.2
'@

Set-Content backend\__init__.py ''
Set-Content backend\app.py $backendApp -Encoding UTF8
Set-Content backend\requirements.txt $backendReq -Encoding UTF8

# --- Frontend files ---
$pkg = @'
{
  "name": "friday-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview --port 5173"
  },
  "devDependencies": {
    "vite": "^5.4.10"
  }
}
'@

$vite = @'
import { defineConfig } from "vite";
export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } }
  },
  build: { outDir: "dist" }
});
'@

$indexHtml = @'
<!doctype html>
<html>
  <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Friday Frontend</title></head>
  <body><div id="app"></div><script type="module" src="/src/main.js"></script></body>
</html>
'@

$mainJs = @'
const root = document.getElementById("app");
root.innerHTML = `
  <h1>Friday Frontend</h1>
  <div>Status: <span id="status">…</span></div>
  <h3>/health</h3><pre id="healthPre"></pre>
  <h3>Ask (wired to POST /api/ask)</h3>
  <form id="askForm"><input id="askInput" placeholder="what did the fox do?" /><button>Ask</button></form>
  <pre id="askPre"></pre>
`;
async function getJSON(url, opts){ const r=await fetch(url,opts); const t=await r.text(); try{ return {ok:r.ok,json:JSON.parse(t)} }catch{ return {ok:r.ok,text:t} } }
(async()=>{ const h=await getJSON('/api/health'); document.getElementById('status').textContent=h.ok?'OK':'ERROR'; document.getElementById('healthPre').textContent=JSON.stringify(h.json??h.text,null,2);})();
document.getElementById('askForm').addEventListener('submit',async e=>{ e.preventDefault(); const q=document.getElementById('askInput').value||''; const r=await getJSON('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})}); document.getElementById('askPre').textContent=JSON.stringify(r.json??r.text,null,2);});
'@

Set-Content frontend\package.json $pkg -Encoding UTF8
Set-Content frontend\vite.config.js $vite -Encoding UTF8
Set-Content frontend\index.html $indexHtml -Encoding UTF8
Set-Content frontend\src\main.js $mainJs -Encoding UTF8

# Clean stray PostCSS config if present (caused your JSON error)
Get-ChildItem frontend -Filter "postcss.config.*" -File -Recurse | Remove-Item -Force -ErrorAction SilentlyContinue

# Python venv + deps
if (-not (Test-Path ".venv")) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r backend\requirements.txt

# Frontend deps
Push-Location frontend
npm install
Pop-Location

Write-Host "`n✔ Bootstrap complete." -ForegroundColor Green
Write-Host "To run locally:"
Write-Host "  1) .\.venv\Scripts\Activate.ps1"
Write-Host "  2) uvicorn backend.app:app --host 0.0.0.0 --port 8000   (from repo root)"
Write-Host "  3) cd frontend && npm run dev"

