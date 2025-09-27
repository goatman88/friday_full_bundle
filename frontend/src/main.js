async function getJSON(url, opts = {}) {
  const res = await fetch(url, opts);
  const text = await res.text();
  try { return { ok: res.ok, data: JSON.parse(text) }; }
  catch { return { ok: res.ok, data: text }; }
}

document.getElementById('btnHealth').addEventListener('click', async () => {
  const out = document.getElementById('healthOut');
  out.textContent = 'checking…';
  const { ok, data } = await getJSON('http://localhost:8000/api/health');
  out.textContent = (ok ? 'OK ' : 'ERR ') + JSON.stringify(data, null, 2);
});

document.getElementById('btnAsk').addEventListener('click', async () => {
  const q = document.getElementById('q').value || 'ping';
  const out = document.getElementById('askOut');
  out.textContent = 'sending…';
  const { ok, data } = await getJSON('http://localhost:8000/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q })
  });
  out.textContent = (ok ? 'OK ' : 'ERR ') + JSON.stringify(data, null, 2);
});









