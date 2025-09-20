// Backend base URL comes from Render env var VITE_API_BASE
// Example: https://friday-099e.onrender.com/api
export const API_BASE = import.meta.env.VITE_API_BASE;

// Simple health check the landing page can call
export async function ping() {
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
