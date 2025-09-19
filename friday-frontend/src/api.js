const API_BASE = import.meta.env.VITE_API_BASE?.replace(/\/$/, '') || ''

export async function health() {
  const r = await fetch(\\/health\)
  return r.ok ? await r.json() : { error: \HTTP \\ }
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
