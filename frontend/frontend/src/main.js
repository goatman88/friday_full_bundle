const out = document.querySelector('#out');
const btn = document.querySelector('#ping');

btn.addEventListener('click', async () => {
  out.textContent = '...';
  try {
    // Use env when deployed, otherwise proxy in dev
    const base = import.meta.env.VITE_BACKEND_URL || '';
    const res = await fetch(`${base}/api/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.textContent = JSON.stringify(data);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});
