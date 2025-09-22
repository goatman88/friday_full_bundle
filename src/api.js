const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173')
  ? '' // use Vite proxy in dev
  : (import.meta.env.VITE_API_BASE || '')

// Basic GET
export async function apiHealth()  { return get('/api/health') }
export async function rootHealth() { return get('/health') }

async function get(path) {
  const res = await fetch(API_BASE + path)
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

// Non-stream ask
export async function ask(q, session_id='default') {
  const res = await fetch(API_BASE + '/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, session_id })
  })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

// SSE stream
export function stream(q, onToken, session_id='default') {
  const u = new URL((API_BASE || '') + '/api/stream', window.location.origin)
  u.searchParams.set('q', q)
  u.searchParams.set('session_id', session_id)
  const es = new EventSource(u.toString())
  es.onmessage = (e) => onToken(e.data)
  es.addEventListener('done', () => es.close())
  es.onerror = () => es.close()
  return () => es.close()
}

// WebSocket stream
export function wsStream(q, onToken, session_id='default') {
  const base = (API_BASE || window.location.origin).replace(/^http/, 'ws')
  const ws = new WebSocket(base + '/ws')
  ws.onopen = () => ws.send(JSON.stringify({ q, session_id }))
  ws.onmessage = (ev) => {
    try {
      const j = JSON.parse(ev.data)
      if (j.done) ws.close()
    } catch {
      onToken(ev.data)
    }
  }
  ws.onerror = () => ws.close()
  return () => ws.close()
}

// Vision upload (image + prompt)
export async function vision(prompt, file, session_id='default') {
  const fd = new FormData()
  fd.append('prompt', prompt)
  fd.append('image', file)
  fd.append('session_id', session_id)
  const res = await fetch(API_BASE + '/api/vision', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

// STT upload (blob -> text)
export async function stt(file) {
  const fd = new FormData()
  fd.append('file', file, 'speech.wav')
  const res = await fetch(API_BASE + '/api/stt', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

// TTS → audio/wav
export async function tts(text) {
  const res = await fetch(API_BASE + '/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  })
  if (!res.ok) throw new Error(await res.text())
  const buf = await res.arrayBuffer()
  return new Blob([buf], { type: 'audio/wav' })
}




