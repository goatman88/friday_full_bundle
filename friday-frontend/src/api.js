// friday-frontend/src/api.js
export const API_BASE = import.meta.env.VITE_API_BASE;

export async function getHealth() {
  const r = await fetch(`${API_BASE}/health`, { method: 'GET' });
  if (!r.ok) throw new Error(`health ${r.status}`);
  return r.json();
}


export async function ragQuery(q) {
  const url = new URL(`${API_BASE}/rag/query`);
  url.searchParams.set('q', q);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`RAG query failed: ${res.status}`);
  return res.json();
}
