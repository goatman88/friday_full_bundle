# setup-frontend.ps1
$ErrorActionPreference = "Stop"

# 1) write .env
Set-Content -Encoding UTF8 .env -Value "VITE_API_BASE=https://friday-099e.onrender.com"

# 2) src files
New-Item -ItemType Directory -Force -Path src | Out-Null

$apiTs = @'
const BASE = import.meta.env.VITE_API_BASE?.trim();

if (!BASE) {
  console.warn("VITE_API_BASE is empty. Set it in .env");
}

export async function apiGet(path: string) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, { credentials: "omit" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function pingBoth() {
  const root = await apiGet("/health");
  const api  = await apiGet("/api/health");
  return { root, api };
}
'@
$apiTs | Set-Content -Encoding UTF8 src/api.ts

$checkTsx = @'
import { useState } from "react";
import { pingBoth } from "./api";

export default function BackendCheck() {
  const [result, setResult] = useState("(click to test)");

  async function test() {
    try {
      const data = await pingBoth();
      setResult(JSON.stringify(data));
    } catch (e: any) {
      setResult(`Error: ${e.message || e}`);
    }
  }

  return (
    <div style={{padding:"12px", border:"1px solid #ddd", borderRadius:6}}>
      <button onClick={test}>Test backend /health + /api/health</button>
      <pre>{result}</pre>
    </div>
  );
}
'@
$checkTsx | Set-Content -Encoding UTF8 src/BackendCheck.tsx

Write-Host "Now open src/App.tsx and add:" -ForegroundColor Yellow
Write-Host '  import BackendCheck from "./BackendCheck";'
Write-Host "  <BackendCheck />" -ForegroundColor Cyan

Write-Host "`nInstalling deps with npm.cmd (Windows-safe)..." -ForegroundColor Green
npm.cmd install

Write-Host "Starting dev server..." -ForegroundColor Green
npm.cmd run dev
