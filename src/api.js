const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173') ? '' : (import.meta.env.VITE_API_BASE || '')

async function go(path, opts = {}) {
  const res = await fetch(API_BASE + path, { headers: { 'Content-Type': 'application/json' }, ...opts })
  const txt = await res.text()
  let body; try { body = JSON.parse(txt) } catch { body = txt }
  if (!res.ok) throw new Error(typeof body === 'string' ? body : JSON.stringify(body))
  return body
}

export const health    = () => go('/health')
export const apiHealth = () => go('/api/health')
export const ask       = (q, session_id='default') => go('/api/ask', { method:'POST', body: JSON.stringify({ q, session_id }) })

export function askStream({ q, session_id='default', onToken, onDone, onError }) {
  const url = API_BASE + `/api/ask/stream?` + new URLSearchParams({ q, session_id })
  const ev = new EventSource(url)
  ev.onmessage = e => {
    if (e.data === "[DONE]") { ev.close(); onDone?.(); return }
    onToken?.(e.data)
  }
  ev.onerror = err => { ev.close(); onError?.(err) }
  return () => ev.close()
}

export function wsChat({ q, session_id='default', onToken, onDone, onError }) {
  const wsUrl = (API_BASE || window.location.origin).replace(/^http/, 'ws') + '/ws/chat'
  const ws = new WebSocket(wsUrl)
  ws.onopen = () => ws.send(JSON.stringify({ q, session_id }))
  ws.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data)
      if (j.done) { onDone?.(); ws.close(); return }
      if (j.error) { onError?.(j.error) }
    } catch {
      onToken?.(e.data) // token chunk
    }
  }
  ws.onerror = e => { onError?.(e) }
  return () => ws.close()
}

// Vision / STT / TTS
export async function vision({ prompt, imageUrl, file }) {
  const form = new FormData()
  form.append('prompt', prompt)
  if (imageUrl) form.append('image_url', imageUrl)
  if (file) form.append('file', file)
  const res = await fetch(API_BASE + '/api/vision', { method:'POST', body: form })
  const j = await res.json(); if (!res.ok) throw new Error(JSON.stringify(j)); return j
}
export async function stt(audioBlob) {
  const form = new FormData(); form.append('audio', audioBlob, 'speech.webm')
  const res = await fetch(API_BASE + '/api/stt', { method:'POST', body: form })
  const j = await res.json(); if (!res.ok) throw new Error(JSON.stringify(j)); return j
}
export async function tts(text) {
  const res = await fetch(API_BASE + '/api/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text }) })
  const j = await res.json(); if (!res.ok) throw new Error(JSON.stringify(j)); return j.audio_wav_b64
}


