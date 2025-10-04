// Build an absolute API base from env at build-time; in dev Vite will proxy /api
const BASE = (import.meta.env?.VITE_BACKEND_URL || "").replace(/\/+$/,"");
const api = (p) => (BASE ? `${BASE}${p}` : p);

async function ping() {
  const res = await fetch(api('/api/health'));
  const txt = await res.text();
  document.getElementById('out').textContent = txt;
}
document.getElementById('ping').addEventListener('click', ping);
















