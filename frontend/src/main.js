const backend = import.meta.env.VITE_BACKEND_URL || window.VITE_BACKEND_URL || "https://friday-backend-ksep.onrender.com";
const r = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/health`);

async function ping() {
  const txt = await res.text();
  document.getElementById('out').textContent = txt;
}
document.getElementById('ping').addEventListener('click', ping);
















