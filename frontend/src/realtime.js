export async function fetchEphemeralSession() {
  const r = await fetch('/api/session', { method: 'POST' });
  if (!r.ok) throw new Error(`session failed: ${r.status}`);
  return await r.json(); // { client_secret: {...} }
}

// Proxy-based WebRTC (safer; API key stays server-side)
export async function sdpExchangeViaServer(offerSdp) {
  const r = await fetch('/api/sdp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: offerSdp
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`SDP proxy error ${r.status}: ${t}`);
  }
  return await r.text(); // answer SDP
}
