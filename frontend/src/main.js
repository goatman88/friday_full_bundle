const app = document.getElementById('app');

async function ping() {
  try {
    const r = await fetch('http://localhost:8000/api/health');
    const j = await r.json();
    return j;
  } catch (e) {
    return { error: String(e) };
  }
}

async function ask(q) {
  const r = await fetch('http://localhost:8000/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q })
  });
  return r.json();
}

(async () => {
  const health = await ping();
  app.innerHTML = `
    <h1>Friday Frontend</h1>
    <pre>health: ${JSON.stringify(health)}</pre>
    <input id="q" placeholder="type a question" />
    <button id="go">Ask</button>
    <pre id="out"></pre>
  `;
  document.getElementById('go').onclick = async () => {
    const q = document.getElementById('q').value || 'ping';
    const res = await ask(q);
    document.getElementById('out').textContent = JSON.stringify(res, null, 2);
  };
})();






