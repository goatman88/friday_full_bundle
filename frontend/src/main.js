// Read at build time on Render; in local dev you can override in .env.local
const BACKEND = import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, '') || '';

const els = {
  status: document.getElementById('status'),
  ping: document.getElementById('ping'),
  out: document.getElementById('out'),
  askForm: document.getElementById('ask-form'),
  askInput: document.getElementById('ask-input'),
  askOut: document.getElementById('ask-out')
};

function setStatus(msg) {
  els.status.textContent = `Status: ${msg}`;
}

async function call(path, opts = {}) {
  const url = `${BACKEND}${path}`;
  const res = await fetch(url, {
    headers: { 'content-type': 'application/json' },
    ...opts
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

els.ping.addEventListener('click', async () => {
  setStatus('Pinging…');
  els.out.textContent = '';
  try {
    // IMPORTANT: always use /api/health (not /health)
    const data = await call('/api/health');
    setStatus('OK');
    els.out.textContent = JSON.stringify(data);
  } catch (e) {
    setStatus('Failed to fetch');
    els.out.textContent = String(e);
  }
});

els.askForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  els.askOut.textContent = '';
  try {
    const q = els.askInput.value || '';
    const data = await call('/api/ask', {
      method: 'POST',
      body: JSON.stringify({ question: q })
    });
    els.askOut.textContent = JSON.stringify(data, null, 2);
  } catch (e2) {
    els.askOut.textContent = String(e2);
  }
});

// show where we're pointing (helps debugging)
setStatus(BACKEND ? `using ${BACKEND}` : 'NO VITE_BACKEND_URL set');









