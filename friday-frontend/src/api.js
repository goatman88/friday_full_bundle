// friday-frontend/src/api.js
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function ragQuery(q) {
  const url = new URL(`${API_BASE}/rag/query`);
  url.searchParams.set('q', q);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`RAG query failed: ${res.status}`);
  return res.json();
}
