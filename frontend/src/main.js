const root = document.getElementById('app');

root.innerHTML = `
  <h1>Friday Frontend</h1>
  <div>Status: <span id="status">…</span></div>

  <h3>/health</h3>
  <pre id="healthPre"></pre>

  <h3>Ask (wired to POST /api/ask)</h3>
  <form id="askForm">
    <input id="askInput" placeholder="what did the fox do?" />
    <button>Ask</button>
  </form>
  <pre id="askPre"></pre>
`;

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  const t = await r.text();
  try { return { ok: r.ok, json: JSON.parse(t) }; }
  catch { return { ok: r.ok, text: t }; }
}

(async () => {
  // /api/health
  const h = await getJSON('/api/health');
  document.getElementById('status').textContent = h.ok ? 'OK' : 'ERROR';
  document.getElementById('healthPre').textContent = JSON.stringify(h.json ?? h.text, null, 2);
})();

document.getElementById('askForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = document.getElementById('askInput').value || '';
  const r = await getJSON('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type':'application/json' },
    body: JSON.stringify({ q })
  });
  document.getElementById('askPre').textContent = JSON.stringify(r.json ?? r.text, null, 2);
});




