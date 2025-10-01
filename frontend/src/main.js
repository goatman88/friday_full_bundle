// frontend/src/main.js

// ---------- API base selection ----------
// In production we read the baked-in env var VITE_BACKEND_URL.
// In local dev we hit the Vite proxy at /api (configured in vite.config.js).
const isProd = import.meta.env.PROD;
const baked = import.meta.env.VITE_BACKEND_URL?.trim();
const API_BASE = (isProd && baked) ? baked : '/api';

// Small helper to build URLs safely
const api = (path) => {
  const p = path.startsWith('/') ? path : `/${path}`;
  return isProd && baked ? `${API_BASE}${p}` : `${API_BASE}${p}`;
};

// ---------- DOM ----------
const out = document.querySelector('#out');
const statusEl = document.querySelector('#status');
const btnPing = document.querySelector('#ping');
const askInput = document.querySelector('#ask');
const askBtn = document.querySelector('#askBtn');
const baseEl = document.querySelector('#base');

if (baseEl) baseEl.textContent = API_BASE || '(not set)';

// ---------- utils ----------
const show = (msg, type = 'info') => {
  const line = document.createElement('div');
  line.textContent = typeof msg === 'string' ? msg : JSON.stringify(msg);
  line.style.whiteSpace = 'pre-wrap';
  line.dataset.type = type;
  out?.prepend(line);
};

const setStatus = (msg, isError = false) => {
  if (!statusEl) return;
  statusEl.textContent = msg;
  statusEl.style.color = isError ? 'crimson' : 'inherit';
};

const fetchJSON = async (url, opts = {}) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 10000);
  try {
    const res = await fetch(url, { signal: ctrl.signal, ...opts });
    const ct = res.headers.get('content-type') || '';
    if (!res.ok) {
      // Try to read JSON error, else text
      let body;
      try { body = ct.includes('json') ? await res.json() : await res.text(); }
      catch { body = '<no body>'; }
      throw new Error(`HTTP ${res.status} ${res.statusText} — ${body}`);
    }
    if (!ct.includes('json')) {
      const text = await res.text();
      throw new Error(`Expected JSON, got: ${text.slice(0, 120)}…`);
    }
    return await res.json();
  } finally {
    clearTimeout(t);
  }
};

// ---------- actions ----------
const doPing = async () => {
  setStatus('Pinging /api/health…');
  try {
    const data = await fetchJSON(api('/api/health'));
    setStatus('OK');
    show(data);
  } catch (err) {
    setStatus('ERROR: Failed to fetch', true);
    show(String(err), 'error');
    // Common CORS hint
    if (String(err).includes('TypeError: Failed to fetch') || String(err).includes('CORS')) {
      show(`Hint: If this is on Render prod, make sure backend CORS allows:
- https://friday-full-bundle.onrender.com
And VITE_BACKEND_URL points to your backend URL.`, 'error');
    }
  }
};

const doAsk = async () => {
  const q = askInput?.value?.trim();
  if (!q) return;
  setStatus('Asking backend…');
  try {
    const data = await fetchJSON(api('/api/ask'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    });
    setStatus('OK');
    show(data);
  } catch (err) {
    setStatus('ERROR: Failed to fetch', true);
    show(String(err), 'error');
  }
};

// ---------- wire up ----------
btnPing?.addEventListener('click', doPing);
askBtn?.addEventListener('click', doAsk);
askInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doAsk();
});

// Initial status
setStatus('Ready');
// Optional: show where we’re pointing
show(`API_BASE = ${API_BASE}`);



