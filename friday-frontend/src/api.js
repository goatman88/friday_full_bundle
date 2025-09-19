const API_BASE = import.meta.env.VITE_API_BASE?.replace(/\/\$/, '') || ''

export async function getHealth() {
  const r = await fetch(\\/health\)
  if (!r.ok) throw new Error(\Health failed: \\)
  return r.json()
}

export async function requestUploadUrl() {
  const r = await fetch(\\/rag/upload_url\, { method: 'POST' })
  if (!r.ok) throw new Error('upload_url failed')
  return r.json()
}

export async function confirmUpload(payload) {
  const r = await fetch(\\/rag/confirm_upload\, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!r.ok) throw new Error('confirm_upload failed')
  return r.json()
}

export async function queryRag(body) {
  const r = await fetch(\\/rag/query\, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!r.ok) throw new Error('query failed')
  return r.json()
}
