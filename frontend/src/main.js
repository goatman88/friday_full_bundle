const API_BASE = 'http://localhost:8000';

const el = (id) => document.getElementById(id);

el('btn-health').addEventListener('click', async () => {
  el('health-out').textContent = '…checking';
  try {
    const r = await fetch(`${API_BASE}/api/health`);
    const j = await r.json();
    el('health-out').textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    el('health-out').textContent = `Health error: ${e}`;
  }
});
import './style.css'

document.querySelector('#app').innerHTML = `
  <h1>Hello Friday!</h1>
  <p>Frontend is working with Vite 🎉</p>
`;

el('btn-ask').addEventListener('click', async () => {
  const q = el('q').value.trim();
  if (!q) { el('ask-out').textContent = 'Enter a question first.'; return; }
  el('ask-out').textContent = '…sending';
  try {
    const r = await fetch(`${API_BASE}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    });
    const j = await r.json();
    el('ask-out').textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    el('ask-out').textContent = `Ask error: ${e}`;
  }
});







