const API_BASE =
  (typeof window !== 'undefined' && window.location.port === '5173')
    ? (import.meta.env.VITE_API_BASE || 'http://localhost:8000')
    : '';

async function go(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts
  });
  if (!res.ok) throw new Error(await res.text());
  return res.headers.get('content-type')?.includes('application/json')
    ? res.json()
    : res.text();
}

export const health      = () => go('/health');
export const apiHealth   = () => go('/api/health');
export const ask         = (q, session_id='default') =>
  go('/api/ask', { method: 'POST', body: JSON.stringify({ q, session_id }) });

export function streamAsk({ q, session_id='default', onToken, onDone, onError }) {
  const url = `${API_BASE}/api/stream?` + new URLSearchParams({ q, session_id });
  const es = new EventSource(url, { withCredentials: false });
  es.onmessage = (e) => {
    if (!e.data) return;
    const payload = JSON.parse(e.data);
    if (payload.token) onToken?.(payload.token);
    if (payload.done) { es.close(); onDone?.(); }
  };
  es.onerror = (e) => { es.close(); onError?.(e); };
  return es;
}

export const getHistory  = (s) => go(`/api/history/${encodeURIComponent(s)}`);
export const addHistory  = (s, entry) =>
  go(`/api/history/${encodeURIComponent(s)}`, { method: 'POST', body: JSON.stringify(entry) });
export const clearHistory = (s) =>
  go(`/api/history/${encodeURIComponent(s)}`, { method: 'DELETE' });

// --- camera snapshot to vision ---
export async function visionFromCanvas(canvas, prompt, session_id='default') {
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
  return go('/api/vision', {
    method: 'POST',
    body: JSON.stringify({ session_id, prompt, image_base64: dataUrl })
  });
}

// --- mic & camera helpers ---
export async function startCamera(videoEl) {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  videoEl.srcObject = stream;
  await videoEl.play();
  return stream;
}
export function snapToCanvas(videoEl, canvasEl) {
  const w = videoEl.videoWidth, h = videoEl.videoHeight;
  canvasEl.width = w; canvasEl.height = h;
  canvasEl.getContext('2d').drawImage(videoEl, 0, 0, w, h);
}

export async function startMic() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return stream; // you can wire to Realtime later
}

// --- realtime websocket skeleton ---
export function connectRealtime(onMessage, onError) {
  const ws = new WebSocket(`${API_BASE.replace('http', 'ws')}/ws/realtime`);
  ws.onmessage = (e) => onMessage?.(e.data);
  ws.onerror   = (e) => onError?.(e);
  return ws;
}








