const backend = "https://friday-backend-ksep.onrender.com";

async function ping() {
  try {
    const r = await fetch(`${backend}/api/health`, { cache: 'no-cache' });
    const t = await r.text();
    const out = document.getElementById('out') || document.body;
    out.textContent = t;
  } catch (e) {
    const out = document.getElementById('out') || document.body;
    out.textContent = `Request failed: ${e}`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('ping');
  if (btn) btn.addEventListener('click', ping);
  // also auto-ping on load for sanity
  ping();
});




