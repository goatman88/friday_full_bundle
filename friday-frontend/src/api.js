// DO NOT put stray backslashes or unmatched quotes in these strings.
// Build uses VITE_API_BASE at deploy; local falls back to localhost:8000/api.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}


export async function confirmUpload(body) {
  const r = await fetch(\\/rag/confirm_upload\, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error('confirm_upload failed')
  return r.json()
}

export async function queryRag(q, top_k = 5, index = 'both') {
  const r = await fetch(\\/rag/query\, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, top_k, index }),
  })
  if (!r.ok) throw new Error('query failed')
  return r.json()
}
