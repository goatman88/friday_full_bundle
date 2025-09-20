export const API_BASE = import.meta.env.VITE_API_BASE;
export async function getHealth() {
  const res = await fetch(${API_BASE}/health, { cache: "no-store" });
  if (!res.ok) throw new Error(HTTP );
  return res.json();
}
