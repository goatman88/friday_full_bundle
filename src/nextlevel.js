const log = (m) => {
  const el = document.getElementById('log');
  el.textContent += `${m}\n`;
  el.scrollTop = el.scrollHeight;
};

const BACKEND = (import.meta.env?.VITE_BACKEND_BASE) || 'http://localhost:8000';

// --- basic health + ask (your existing endpoints)
async function loadHealth() {
  const h1 = await fetch(`${BACKEND}/health`).then(r=>r.json()).catch(()=>({status:'ERROR'}));
  const h2 = await fetch(`${BACKEND}/api/health`).then(r=>r.json()).catch(()=>({status:'ERROR'}));
  document.getElementById('status').textContent = (h1.status==='ok' && h2.status==='ok') ? 'OK' : 'ERROR';
  document.getElementById('health').textContent = JSON.stringify(h1);
  document.getElementById('apihealth').textContent = JSON.stringify(h2);
}
loadHealth();

document.getElementById('rtConnect').onclick = async () => {
  const out = document.getElementById('rtLog');
  out.textContent = 'connecting…';

  // Browser-only WebRTC to our server proxy (no API key in browser)
  const pc = new RTCPeerConnection();
  const dc = pc.createDataChannel('events');
  dc.onmessage = e => { out.textContent = e.data; log(`oai: ${e.data}`); };

  // Mic up
  const mic = await navigator.mediaDevices.getUserMedia({audio:true});
  mic.getTracks().forEach(t => pc.addTrack(t, mic));

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  // Send SDP offer to backend proxy -> forwards to OpenAI -> returns answer SDP
  const resp = await fetch(`${BACKEND}/api/realtime/sdp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: offer.sdp
  });
  if (!resp.ok) {
    out.textContent = `proxy error ${resp.status}`;
    return;
  }
  const answerSdp = await resp.text();
  await pc.setRemoteDescription({type:'answer', sdp:answerSdp});
  out.textContent = 'connected';
};


// --- B) SSE
document.getElementById('sseBtn').onclick = () => {
  const p = document.getElementById('ssePrompt').value || 'hello';
  const out = document.getElementById('sseOut');
  out.textContent = '';
  const es = new EventSource(`${BACKEND}/api/stream?prompt=${encodeURIComponent(p)}`);
  es.onmessage = (e) => { out.textContent += e.data; };
  es.onerror = () => es.close();
};

// --- C) WebSocket chat
let sock;
document.getElementById('wsOpen').onclick = () => {
  sock = new WebSocket(`ws://${location.hostname}:8000/ws/chat`);
  const out = document.getElementById('wsOut');
  sock.onopen = ()=> out.textContent = 'opened';
  sock.onmessage = (e)=> out.textContent = e.data;
  sock.onclose = ()=> out.textContent = 'closed';
};
document.getElementById('wsSend').onclick = () => sock?.send('hello');
document.getElementById('wsClose').onclick = () => sock?.close();

// --- D) Camera
let stream;
document.getElementById('camStart').onclick = async () => {
  stream = await navigator.mediaDevices.getUserMedia({video:true, audio:false});
  document.getElementById('cam').srcObject = stream;
};
document.getElementById('camSnap').onclick = () => {
  if(!stream) return;
  const v = document.getElementById('cam');
  const c = document.getElementById('snap');
  c.getContext('2d').drawImage(v,0,0,c.width,c.height);
};
document.getElementById('camStop').onclick = () => { stream?.getTracks().forEach(t=>t.stop()); };

// --- E) Press-to-talk: MediaRecorder -> /api/stt -> /api/ask -> /api/tts
let rec, chunks=[];
document.getElementById('pttStart').onmousedown = async () => {
  const s = await navigator.mediaDevices.getUserMedia({audio:true});
  rec = new MediaRecorder(s);
  rec.ondataavailable = e => chunks.push(e.data);
  rec.onstop = async () => {
    const blob = new Blob(chunks,{type:'audio/webm'}); chunks=[];
    const form = new FormData(); form.append('file', blob, 'ptt.webm');
    const stt = await fetch(`${BACKEND}/api/stt`, {method:'POST', body:form}).then(r=>r.json()).catch(()=>({text:'(stt failed)'}));
    document.getElementById('pttText').textContent = stt.text || '(no text)';
    // Ask
    let answerText = '(ask not implemented)';
    try {
      const ans = await fetch(`${BACKEND}/api/ask`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({q: stt.text})
      }).then(r=>r.json());
      answerText = ans.text ?? JSON.stringify(ans);
    } catch {}
    // TTS
    try {
      const audio = await fetch(`${BACKEND}/api/tts`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text: answerText})
      }).then(r=>r.blob());
      new Audio(URL.createObjectURL(audio)).play();
    } catch {}
  };
  rec.start();
};
document.getElementById('pttStop').onmouseup = () => rec?.stop();

// --- G) OpenAI Realtime (browser-only quick start)
document.getElementById('rtConnect').onclick = async () => {
  const out = document.getElementById('rtLog');
  out.textContent = 'connecting…';
  // For production, proxy token exchange via backend. For a quick test:
  const OPENAI_REALTIME_URL = 'https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview';
  const OPENAI_API_KEY = (window.OPENAI_API_KEY || '') // set via dev only, or swap to backend proxy
  if(!OPENAI_API_KEY){ out.textContent='Set OPENAI_API_KEY in window for dev, or add a backend proxy.'; return; }

  const pc = new RTCPeerConnection();
  const dc = pc.createDataChannel('oai-events');
  dc.onmessage = (e)=> { out.textContent = e.data; log(`oai: ${e.data}`); };

  const mic = await navigator.mediaDevices.getUserMedia({audio:true});
  mic.getTracks().forEach(t => pc.addTrack(t, mic));

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const resp = await fetch(OPENAI_REALTIME_URL, {
    method:'POST',
    headers:{ 'Authorization': `Bearer ${OPENAI_API_KEY}`, 'Content-Type':'application/sdp' },
    body: offer.sdp
  });
  const answer = await resp.text();
  await pc.setRemoteDescription({type:'answer', sdp:answer});
  out.textContent = 'connected';
};

