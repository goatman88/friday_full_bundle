import React, { useEffect, useRef, useState } from 'react';
import {
  health, apiHealth, ask, streamAsk,
  startCamera, snapToCanvas, visionFromCanvas,
  getHistory, clearHistory
} from './api';

export default function App() {
  const [status, setStatus] = useState('checking…');
  const [h1, setH1] = useState('');
  const [h2, setH2] = useState('');
  const [q, setQ] = useState('what did the fox do?');
  const [answer, setAnswer] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [session, setSession] = useState('demo');

  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const [a, b] = await Promise.all([health(), apiHealth()]);
        setH1(JSON.stringify(a)); setH2(JSON.stringify(b));
        setStatus('OK');
      } catch {
        setStatus('ERROR');
      }
    })();
  }, []);

  const onAsk = () => {
    setAnswer(''); setStreaming(true);
    streamAsk({
      q, session_id: session,
      onToken: t => setAnswer(s => s + t),
      onDone: () => setStreaming(false),
      onError: () => setStreaming(false),
    });
  };

  const onStartCam = async () => { await startCamera(videoRef.current); };
  const onSnap = async () => {
    snapToCanvas(videoRef.current, canvasRef.current);
    const res = await visionFromCanvas(canvasRef.current, "What's in this frame?", session);
    setAnswer(res.answer);
  };

  return (
    <div style={{ fontFamily:'system-ui, sans-serif', padding:24, lineHeight:1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      {/* ===== CAMERA FIRST, NICE & BIG ===== */}
      <section style={{ border:'1px solid #ddd', padding:12, borderRadius:8, marginBottom:16 }}>
        <h3>Camera (press to snap → /api/vision)</h3>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
          <video ref={videoRef} style={{ width:'100%', background:'#000', minHeight:220 }} />
          <canvas ref={canvasRef} style={{ width:'100%', background:'#222', minHeight:220 }} />
        </div>
        <div style={{ marginTop:8, display:'flex', gap:8 }}>
          <button onClick={onStartCam}>Start camera</button>
          <button onClick={onSnap}>Snap → Vision</button>
        </div>
      </section>

      {/* ===== HEALTH ===== */}
      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{h1}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{h2}</pre>

      {/* ===== ASK (SSE stream) ===== */}
      <div style={{ marginTop:16 }}>
        <label>Session:&nbsp;</label>
        <input value={session} onChange={e => setSession(e.target.value)} />
        <button onClick={() => clearHistory(session)} style={{ marginLeft:8 }}>Clear history</button>
      </div>

      <h3>Ask (wired to stream /api/stream)</h3>
      <div style={{ display:'flex', gap:8 }}>
        <input style={{ flex:1, padding:8 }} value={q} onChange={e=>setQ(e.target.value)} />
        <button onClick={onAsk} disabled={streaming}>Ask</button>
      </div>

      {answer && (
        <>
          <h4>Answer</h4>
          <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{answer}</pre>
        </>
      )}
    </div>
  );
}














