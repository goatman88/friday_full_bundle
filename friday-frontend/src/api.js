export async function getHealth() {
  const API_BASE = import.meta.env.VITE_API_BASE;      // e.g. https://friday-099e.onrender.com/api
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error(`Health ${r.status}`);
  return r.json();
}



