const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
document.getElementById('base').textContent = API_BASE;

const $health = document.getElementById('health');
const $form = document.getElementById('ask-form');
const $q = document.getElementById('q');
const $send = document.getElementById('send');
const $out = document.getElementById('out');

async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/api/health`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const j = await r.json();
    $health.innerHTML = `<span class="ok">✓ Health:</span> ${JSON.stringify(j)}`;
  } catch (err) {
    $health.innerHTML = `<span class="bad">✗ Health failed:</span> ${String(err)}`;
  }
}

$form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = $q.value.trim();
  if (!q) return;
  $send.disabled = true;
  $out.textContent = 'Thinking…';

  try {
    const r = await fetch(`${API_BASE}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const j = await r.json();
    $out.textContent = JSON.stringify(j, null, 2);
  } catch (err) {
    $out.textContent = `Error: ${String(err)}`;
  } finally {
    $send.disabled = false;
  }
});

checkHealth();
