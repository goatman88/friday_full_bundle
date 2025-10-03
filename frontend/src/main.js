// ---- tiny helper to build absolute URLs from your backend base ----
const BASE = import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, '') || '';
const api = (path) => `${BASE}${path.startsWith('/') ? path : `/${path}`}`;

const out = document.getElementById('out');
const pingBtn = document.getElementById('ping');
const baseEl = document.getElementById('base');
const askForm = document.getElementById('ask-form');
const askInput = document.getElementById('ask-input');

// show which backend we’re talking to
baseEl.textContent = `Backend: ${BASE || '(missing VITE_BACKEND_URL)'}`;

// generic GET helper (handles network + HTTP errors into one message)
async function getJSON(url) {
  try {
    const res = await fetch(url, { method: 'GET' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    throw new Error(err.message || 'Failed to fetch');
  }
}

// wire the “Ping backend” button to /api/health (on the backend host)
pingBtn.addEventListener('click', async () => {
  out.textContent = '…';
  try {
    const data = await getJSON(api('/api/health'));
    out.textContent = JSON.stringify(data);
  } catch (e) {
    out.textContent = `Error: ${e.message}`;
  }
});

// simple demo form wired to POST /api/ask
askForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  out.textContent = '…';
  try {
    const res = await fetch(api('/api/ask'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: askInput.value || '' }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.textContent = JSON.stringify(data);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});










