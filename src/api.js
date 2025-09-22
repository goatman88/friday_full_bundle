const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173')
  ? '' // dev proxy
  : import.meta.env.VITE_API_BASE || ''

async function go(path, opts = {}) {
  const url = API_BASE + path
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
  const txt = await res.text()
  let body
  try { body = JSON.parse(txt) } catch { body = txt }
  if (!res.ok) throw new Error(typeof body === 'string' ? body : JSON.stringify(body))
  return body
}

export const health = () => go('/health')
export const apiHealth = () => go('/api/health')

export const ask = (q) => go('/api/ask', { method: 'POST', body: JSON.stringify({ q }) })

// Vision: send URL or file
export async function vision({ prompt, imageUrl, file }) {
  const form = new FormData()
  form.append('prompt', prompt)
  if (imageUrl) form.append('image_url', imageUrl)
  if (file) form.append('file', file)
  const res = await fetch(API_BASE + '/api/vision', { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(JSON.stringify(data))
  return data
}

// STT: send audio blob
export async function stt(audioBlob) {
  const form = new FormData()
  form.append('audio', audioBlob, 'speech.webm')
  const res = await fetch(API_BASE + '/api/stt', { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(JSON.stringify(data))
  return data
}

// TTS: get wav b64 and return AudioBufferSource
export async function tts(text) {
  const res = await fetch(API_BASE + '/api/tts', { method: 'POST', body: JSON.stringify({ text }), headers: { 'Content-Type': 'application/json' } })
  const data = await res.json()
  if (!res.ok) throw new Error(JSON.stringify(data))
  return data.audio_wav_b64
}

