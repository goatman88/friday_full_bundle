// src/api.js
const API_BASE =
  (typeof window !== 'undefined' && window.location.port === '5173')
    ? '' // dev: use Vite proxy
    : (import.meta.env.VITE_API_BASE || '');

async function go(path, opts = {}) {
  const u = (API_BASE || '').replace(/\/$/, '') + path;
  const res = await fetch(u, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const txt = await res.text();
  let body; try { body = JSON.parse(txt); } catch { body = txt; }
  if (!res.ok) throw new Error(typeof body === 'string' ? body : JSON.stringify(body));
  return body;
}

export const health = () => go('/health');
export const apiHealth = () => go('/api/health');
export const ask = (q) => go('/api/ask', { method: 'POST', body: JSON.stringify({ q }) });

// SSE stream
export function streamAnswer(q, { onToken, onDone, session_id = 'default' } = {}) {
  const u = (API_BASE || '').replace(/\/$/, '') + '/api/stream';
  const ctr = new AbortController();
  fetch(u, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, session_id }),
    signal: ctr.signal,
  }).then(async (res) => {
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      for (;;) {
        const idx = buf.indexOf('\n\n');
        if (idx === -1) break;
        const line = buf.slice(0, idx); buf = buf.slice(idx + 2);
        if (line.startsWith('event: done')) { onDone && onDone(); continue; }
        if (line.startsWith('data: ')) {
          onToken && onToken(line.slice(6));
        }
      }
    }
  });
  return () => ctr.abort();
}

// WebSocket helper
export function openWS(onMsg) {
  const base = (API_BASE || window.location.origin).replace(/^http/, 'ws');
  const ws = new WebSocket(base + '/ws');
  ws.onmessage = (e) => onMsg && onMsg(e.data);
  return ws;
}





