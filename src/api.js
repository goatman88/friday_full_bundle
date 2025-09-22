const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173')
  ? '' // dev uses proxy
  : (import.meta.env.VITE_API_BASE || '');

export async function apiHealth() {
  const r1 = fetch(`${API_BASE}/health`).then(r=>r.text()).catch(()=> 'ERR')
  const r2 = fetch(`${API_BASE}/api/health`).then(r=>r.text()).catch(()=> 'ERR')
  const [h1, h2] = await Promise.all([r1, r2])
  return { h1, h2 }
}

export function streamAsk({ q, session, onDelta, onDone, onError }) {
  const url = `${API_BASE}/api/ask/stream`
  const ctrl = new AbortController()
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type':'application/json' },
    body: JSON.stringify({ q, session }),
    signal: ctrl.signal
  }).then(async res => {
    const dec = new TextDecoder()
    const reader = res.body.getReader()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      for (const line of buf.split('\n\n')) {
        if (!line.startsWith('data:')) continue
        const json = line.slice(5).trim()
        if (json === '[DONE]') { onDone?.(); return }
        try { const o = JSON.parse(json); onDelta?.(o.delta) } catch {}
      }
      buf = ''
    }
  }).catch(e => onError?.(e))
  return () => ctrl.abort()
}

export function wsChat({ session, onDelta, onDone, onError }) {
  const base = API_BASE || `${location.protocol}//${location.host}`
  const wsUrl = base.replace(/^http/i,'ws') + '/ws/chat'
  const ws = new WebSocket(wsUrl)
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.delta) onDelta?.(msg.delta)
    if (msg.done) onDone?.()
  }
  ws.onerror = onError
  return {
    send: (q) => ws.send(JSON.stringify({ q, session })),
    close: () => ws.close()
  }
}






