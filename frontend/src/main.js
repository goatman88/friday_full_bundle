// frontend/src/main.js
const BACKEND = (import.meta.env.VITE_BACKEND_URL || '')
  .replace(/\/+$/, ''); // strip trailing slashes

function api(path) {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${BACKEND}${p}`;
}

const baseEl = document.getElementById('base');
const outEl  = document.getElementById('out');
const pingBtn = document.getElementById('ping');

baseEl.textContent = `Backend: ${BACKEND || '(unset!)'}`;

async function ping() {
  outEl.textContent = '…calling /api/health';
  try {
    const res = await fetch(api('/api/health'), { method: 'GET' });
    if (!res.ok) {
      outEl.textContent = `Error: HTTP ${res.status}`;
      return;
    }
    const body = await res.json();
    outEl.textContent = JSON.stringify(body);
  } catch (err) {
    outEl.textContent = `Error: ${err.message || err}`;
  }
}

pingBtn.addEventListener('click', ping);











