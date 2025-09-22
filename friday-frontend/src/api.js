const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173')
  ? '' // dev -> use proxy
  : (import.meta.env.VITE_API_BASE || '');

async function go(path, opts={}) {
  const u = (API_BASE?.replace(/\/$/, '') || '') + path;
  const res = await fetch(u, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const txt = await res.text();
  let body;
  try { body = JSON.parse(txt); } catch { body = txt; }
  if (!res.ok) throw new Error(typeof body === 'string' ? body : JSON.stringify(body));
  return body;
}

export const health = () => go('/health');
export const apiHealth = () => go('/api/health');

export const ask = (q) => go('/api/ask', {
  method: 'POST',
  body: JSON.stringify({ q })
});
