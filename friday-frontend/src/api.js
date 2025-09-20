export const API_BASE = import.meta.env.VITE_API_BASE;
export async function ping() {
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
