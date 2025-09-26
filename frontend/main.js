const API = (path) => `http://localhost:8000${path}`; // adjust if backend URL changes

document.getElementById('btnHealth').addEventListener('click', async () => {
  const out = document.getElementById('healthOut');
  out.textContent = 'Loading...';
  try {
    const r = await fetch(API('/api/health'));
    out.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});

document.getElementById('btnAsk').addEventListener('click', async () => {
  const out = document.getElementById('askOut');
  const q = document.getElementById('q').value || 'ping';
  out.textContent = 'Loading...';
  try {
    const r = await fetch(API('/api/ask'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ q })
    });
    out.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});

