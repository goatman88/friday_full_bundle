const API_BASE = (typeof window !== 'undefined' && window.location.port === '5173')
  ? '' : import.meta.env.VITE_API_BASE || '';

export async function streamAsk(session_id, q, onToken){
  const res = await fetch(`${API_BASE}/api/ask/stream`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({session_id, q})
  });
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while(true){
    const {value, done} = await reader.read(); if(done) break;
    buf += dec.decode(value, {stream:true});
    const chunks = buf.split('\n\n'); buf = chunks.pop() || '';
    for(const c of chunks){
      if(!c.startsWith('data:')) continue;
      const payload = JSON.parse(c.slice(5).trim());
      if(payload.delta) onToken(payload.delta);
    }
  }
}

export async function uploadImage(file){
  const fd = new FormData(); fd.append('file', file);
  const r = await fetch(`${API_BASE}/api/vision`, { method:'POST', body: fd });
  return r.json();
}

export async function stt(file){
  const fd = new FormData(); fd.append('file', file);
  const r = await fetch(`${API_BASE}/api/stt`, { method:'POST', body: fd });
  return r.json();
}

export async function tts(text){
  const r = await fetch(`${API_BASE}/api/tts`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({text})
  });
  return r.blob(); // audio/mpeg
}







