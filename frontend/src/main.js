// frontend/src/main.js
const out = document.querySelector('#out');
const btn = document.querySelector('#ping');

btn.addEventListener('click', async () => {
  out.textContent = '...';
  try {
    // in dev this goes through the Vite proxy to localhost:8000
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.textContent = JSON.stringify(data);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});




