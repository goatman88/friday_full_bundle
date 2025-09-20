// Backend base URL comes from Render env var VITE_API_BASE
// Example: https://friday-099e.onrender.com/api
export const API_BASE = import.meta.env.VITE_API_BASE;

export async function health() {
  const r = await j('/api/health');
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}


