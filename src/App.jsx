import React, { useEffect, useRef, useState } from 'react'
import { apiHealth, streamAsk, wsChat } from './api'
import { startCamera, snapToCanvas } from './camera'
import { getMicStream, recordMicToChunks } from './mic'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [h1, setH1] = useState(''); const [h2, setH2] = useState('')
  const [q, setQ] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')
  const [mode, setMode] = useState('sse') // sse | ws
  const [session] = useState('demo') // static for now

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const cancelRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => {
    apiHealth().then(({h1,h2}) => { setH1(h1); setH2(h2); setStatus('OK') })
      .catch(() => setStatus('ERROR'))
  }, [])

  const onAsk = () => {
    setAnswer('')
    if (mode === 'sse') {
      cancelRef.current = streamAsk({
        q, session,
        onDelta: (d) => setAnswer(a => a + d),
        onDone: () => (cancelRef.current = null),
        onError: () => (cancelRef.current = null)
      })
    } else {
      wsRef.current = wsChat({
        session,
        onDelta: (d) => setAnswer(a => a + d),
        onDone: () => wsRef.current?.close()
      })
      wsRef.current.send(q)
    }
  }

  const onStartCam = async () => { await startCamera(videoRef.current) }
  const onSnap = () => {
    const dataUrl = snapToCanvas(videoRef.current, canvasRef.current)
    console.log('captured image', dataUrl.slice(0,64)+'...')
  }

  const onMic = async () => {
    const s = await getMicStream()
    const stop = recordMicToChunks(s, (blob) => {
      // TODO: send audio blobs to backend / OpenAI Realtime
      console.log('audio chunk', blob.size)
    })
    setTimeout(stop, 5000)
  }

  return (
    <div style={{ fontFamily:'system-ui, sans-serif', padding: 24, lineHeight: 1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h1)}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h2)}</pre>

      <div style={{ margin:'24px 0' }} />
      <div style={{ display:'flex', gap:8, alignItems:'center' }}>
        <select value={mode} onChange={e=>setMode(e.target.value)}>
          <option value="sse">SSE</option>
          <option value="ws">WebSocket</option>
        </select>
        <input style={{ flex:1, padding:8 }} value={q} onChange={e=>setQ(e.target.value)} placeholder="ask..." />
        <button onClick={onAsk}>Ask</button>
      </div>
      <h4>Answer</h4>
      <pre style={{ background:'#111', color:'#0f0', padding:12, minHeight:80, overflow:'auto' }}>{answer}</pre>

      <div style={{ margin:'24px 0' }} />
      <h3>Camera</h3>
      <div style={{ display:'flex', gap:12 }}>
        <video ref={videoRef} style={{ width:320, height:180, background:'#000' }} />
        <canvas ref={canvasRef} style={{ width:320, height:180, border:'1px solid #333' }}/>
      </div>
      <div style={{ marginTop:8, display:'flex', gap:8 }}>
        <button onClick={onStartCam}>Start Camera</button>
        <button onClick={onSnap}>Snap</button>
      </div>

      <div style={{ margin:'24px 0' }} />
      <h3>Microphone</h3>
      <button onClick={onMic}>Record 5s</button>
    </div>
  )
}












