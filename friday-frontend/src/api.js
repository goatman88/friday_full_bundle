const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}


export async function getUploadUrl() {
  const r = await fetch(\\/rag/upload_url\, { method: 'POST' })
  if (!r.ok) throw new Error('upload_url failed')
  return r.json()
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
