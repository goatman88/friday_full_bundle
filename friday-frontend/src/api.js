// C:\Users\mtw27\friday-frontend\friday-frontend\src\api.js

const API_BASE =
  (import.meta?.env && import.meta.env.VITE_API_BASE) ? import.meta.env.VITE_API_BASE : '';

function j(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  return fetch(url, opts);
}

export async function health() {
  const r = await fetch(`${import.meta.env.VITE_API_BASE}/health`)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

export async function getUploadUrl() {
  const r = await j('/rag/upload_url', { method: 'POST' });
  if (!r.ok) throw new Error('upload_url failed');
  return r.json();
}

export async function confirmUpload(body) {
  const r = await j('/rag/confirm_upload', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('confirm_upload failed');
  return r.json();
}

export async function queryRag({ q, top_k = 5, index = 'both' }) {
  const r = await j('/query_rag', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, top_k, index }),
  });
  if (!r.ok) throw new Error('query_rag failed');
  return r.json();
}
