// frontend/src/main.js

// If VITE_BACKEND_URL is set (production), use it. Otherwise, in dev we rely on the Vite proxy.
const BACKEND = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, ''); // strip trailing slash

const app = document.getElementById('app');
app.innerHTML = `
  <h1>Friday Frontend</h1>
  <button id="ping">Ping backend</button>
  <pre id="out" style="padding:12px;background:#f6f8fa;border:1px solid #ddd;border-radius:6px"></pre>
`;

async function callApi(path, options = {}) {
  // If BACKEND is set (prod), call absolute URL; else call the relative /api (Vite proxy in dev).
  const url = BACKEND ? `${BACKEND}${path}` : path;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

document.getElementById('ping').addEventListener('click', async () => {
  const out = document.getElementById('out');
  out.textContent = 'Pinging...';
  try {
    const data = await callApi('/api/health');
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});

