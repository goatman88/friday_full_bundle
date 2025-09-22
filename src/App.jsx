import React, { useEffect, useRef, useState } from 'react'
import { streamAsk, uploadImage, stt, tts } from './api'

export default function App(){
  const [status, setStatus] = useState('checking...')
  const [q, setQ] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')
  const [session, ] = useState(()=>crypto.randomUUID())

  useEffect(() => { fetch('/api/health').then(()=>setStatus('OK')).catch(()=>setStatus('ERROR')) }, [])

  const onAsk = async () => {
    setAnswer('')
    await streamAsk(session, q, tok => setAnswer(a => a + tok))
  }

  // ---- camera snap ----
  const videoRef = useRef()
  const canvasRef = useRef()

  const startCam = async () => {
    const s = await navigator.mediaDevices.getUserMedia({video:true})
    videoRef.current.srcObject = s
    await videoRef.current.play()
  }
  const snap = async () => {
    const v = videoRef.current; const c = canvasRef.current
    c.width = v.videoWidth; c.height = v.videoHeight
    const ctx = c.getContext('2d'); ctx.drawImage(v,0,0,c.width,c.height)
    const blob = await new Promise(r => c.toBlob(r,'image/jpeg',0.92))
    const out = await uploadImage(new File([blob], 'snap.jpg', {type:'image/jpeg'}))
    setAnswer(out.answer)
  }

  // ---- mic record to wav and STT ----
  const mediaRec = useRef(null)
  const chunks = useRef([])
  const startRec = async () => {
    const s = await navigator.mediaDevices.getUserMedia({audio:true})
    mediaRec.current = new MediaRecorder(s, {mimeType:'audio/webm'})
    chunks.current = []
    mediaRec.current.ondataavailable = e => e.data.size && chunks.current.push(e.data)
    mediaRec.current.onstop = async () => {
      const blob = new Blob(chunks.current, {type:'audio/webm'})
      const wav = new File([blob], 'speech.webm', {type:'audio/webm'})
      const res = await stt(wav)
      const text = res.text || res.results?.[0]?.alternatives?.[0]?.transcript || ''
      setQ(text)
    }
    mediaRec.current.start()
  }
  const stopRec = () => mediaRec.current && mediaRec.current.stop()

  // ---- speak answer ----
  const speak = async () => {
    const audio = new Audio(URL.createObjectURL(await tts(answer || 'Hello')))
    audio.play()
  }

  return (
    <div style={{fontFamily:'system-ui, sans-serif', padding:24}}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>Ask (SSE streaming)</h3>
      <div style={{display:'flex', gap:8}}>
        <input style={{flex:1}} value={q} onChange={e=>setQ(e.target.value)} />
        <button onClick={onAsk}>Ask</button>
        <button onClick={speak}>🔊 Speak</button>
      </div>
      <pre style={{background:'#111', color:'#0f0', padding:12, minHeight:80, whiteSpace:'pre-wrap'}}>{answer}</pre>

      <h3>Camera</h3>
      <div style={{display:'flex', gap:12, alignItems:'center'}}>
        <video ref={videoRef} width="320" height="240" muted />
        <canvas ref={canvasRef} style={{display:'none'}} />
        <div style={{display:'grid', gap:8}}>
          <button onClick={startCam}>Start Camera</button>
          <button onClick={snap}>Snap & Describe</button>
        </div>
      </div>

      <h3>Microphone (press to talk → STT)</h3>
      <div style={{display:'flex', gap:8}}>
        <button onMouseDown={startRec} onMouseUp={stopRec}>Hold to Record</button>
      </div>

      <p style={{opacity:.6, marginTop:24}}>session: {session}</p>
    </div>
  )
}












