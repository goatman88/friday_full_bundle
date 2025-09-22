const BASE = import.meta.env.VITE_BACKEND_BASE;
const SESSION_ID = import.meta.env.VITE_SESSION_ID || 'local';

export async function askOnce(text, imageDataUrl) {
  const r = await fetch(`${BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: SESSION_ID, message: text, image_data_url: imageDataUrl ?? null })
  });
  return r.json();
}

export function sse(text, onToken, onDone, imageDataUrl) {
  const ctrl = new AbortController();
  fetch(`${BASE}/api/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: ctrl.signal,
    body: JSON.stringify({ session_id: SESSION_ID, message: text, image_data_url: imageDataUrl ?? null })
  }).then(async res => {
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += dec.decode(value, { stream: true });
      for (const chunk of buffer.split('\n\n')) {
        if (!chunk.trim()) continue;
        if (chunk.startsWith('data: ')) onToken(chunk.slice(6));
        if (chunk.startsWith('event: done')) onDone?.();
      }
      buffer = '';
    }
  });
  return () => ctrl.abort();
}

export function wsStream(text, onToken, onDone) {
  const ws = new WebSocket(`${BASE.replace('http', 'ws')}/ws/stream`);
  ws.onopen = () => ws.send(JSON.stringify({ session_id: SESSION_ID, message: text }));
  ws.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data);
      if (j.event === 'done') onDone?.();
    } catch {
      onToken(e.data);
    }
  };
  ws.onerror = (e) => console.error(e);
  return () => ws.close();
}

export async function getHistory() {
  const r = await fetch(`${BASE}/api/history/${SESSION_ID}`);
  return r.json();
}
