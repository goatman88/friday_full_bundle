// Minimal API client used by the homepage health check

// Ensure no trailing slash so `${API_BASE}/health` is correct
export const API_BASE = String(import.meta?.env?.VITE_API_BASE ?? '').replace(/\/$/, '');

export async function health() {
  if (!API_BASE) throw new Error('VITE_API_BASE is not set');
  const r = await fetch(`${API_BASE}/health`, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// at the bottom of src/api.js
export const getHealth = health;


