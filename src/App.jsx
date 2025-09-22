// src/App.jsx
import React, { useEffect, useState } from 'react';
import { health, apiHealth, ask, streamAnswer, openWS } from './api';
import CameraCapture from './CameraCapture.jsx';

export default function App() {
  const [status, setStatus] = useState('checking…');
  const [h1, setH1] = useState('');
  const [h2, setH2] = useState('');
  const [q, setQ] = useState('What did the fox do?');
  const [answer, setAnswer] = useState('');
  const [wsMsg, setWsMsg] = useState('');

  useEffect(() => {
    health().then(r => setH1(r.status)).catch(()=>setH1('ERR'));
    apiHealth().then(r => setH2(r.status)).catch(()=>setH2('ERR'));
    Promise.allSettled([health(), apiHealth()])
      .then(([a,b]) => setStatus(a.status==='fulfilled' && b.status==='fulfilled' ? 'OK' : 'ERROR'));
  }, []);

  // WebSocket demo
  function connectWS() {
    const ws = openWS((msg) => setWsMsg(msg));
    ws.onopen = () => ws.send('hello from client');
  }

  function onAsk() {
    setAnswer('');
    streamAnswer(q, {
      onToken: (t) => setAnswer((s) => s + t),
      onDone: () => setAnswer((s) => s + '\n[done]')
    });
  }

  async function onSnap(blob) {
    const res = await fetch('/api/vision/analyze', { method: 'POST', body: (f => { const fd=new FormData(); fd.append('file', f, 'snap.jpg'); return fd; })(new File([blob],'snap.jpg',{type:'image/jpeg'})) });
    console.log(await res.json());
    alert('Uploaded snapshot!');
  }

  return (
    <div style={{ fontFamily:'system-ui, sans-serif', padding:24, lineHeight:1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h1)}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h2)}</pre>

      <h3>SSE Streaming (/api/stream)</h3>
      <div style={{ display:'flex', gap:8 }}>
        <input style={{ flex:1, padding:8 }} value={q} onChange={e=>setQ(e.target.value)} />
        <button onClick={onAsk}>Stream</button>
      </div>
      {answer && (
        <>
          <h4>Answer (live)</h4>
          <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{answer}</pre>
        </>
      )}

      <h3>WebSocket (/ws)</h3>
      <button onClick={connectWS}>Open WS</button>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{wsMsg}</pre>

      <h3>Camera capture</h3>
      <CameraCapture onSnap={onSnap} />
    </div>
  );
}











