export const API_BASE = String(import.meta?.env?.VITE_API_BASE ?? "").replace(/\/$/, "");
export async function health() {
  if (!API_BASE) throw new Error("VITE_API_BASE is not set");
  const r = await fetch(`${API_BASE}/health`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// Alias for old imports
export const getHealth = health;
