const backend = import.meta.env.VITE_BACKEND_URL;
const api = (p) => (BASE ? `${BASE}${p}` : p);

async function ping() {
  const res = await fetch(api('/api/health'));
  const txt = await res.text();
  document.getElementById('out').textContent = txt;
}
document.getElementById('ping').addEventListener('click', ping);
















