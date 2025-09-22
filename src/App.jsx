import React, { useEffect, useRef, useState } from 'react'
import { rootHealth, apiHealth, ask, stream, wsStream, vision, stt, tts } from './api'

export default function App() {
  const [status, setStatus] = useState('checking…')
  const [h1, setH1] = useState(''); const [h2, setH2] = useState('')
  const [q, setQ] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')
  const [streaming, setStreaming] = useState(false)

  const [imgFile, setImgFile] = useState(null)
  const [imgPrompt, setImgPrompt] = useState('Describe this image')

  const [recording, setRecording] = useState(false)
  const mediaRecRef = useRef(null)
  const chunksRef = useRef([])

  useEffect(() => {
    Promise.all([rootHealth(), apiHealth()])
      .then(([a,b]) => { setH1(a.status); setH2(b.status); setStatus('OK') })
      .catch(() => setStatus('ERROR'))
  }, [])

  async function onAsk() {
    const { answer } = await ask(q)
    setAnswer(answer)
  }

  function onSSE() {
    setAnswer(''); setStreaming(true)
    const stop = stream(q, (tok) => setAnswer(a => a + tok))
    // store stop if you want to cancel
  }

  function onWS() {
    setAnswer(''); setStreaming(true)
    wsStream(q, (tok) => setAnswer(a => a + tok))
  }

  async function onVision() {
    if (!imgFile) return
    const { answer } = await vision(imgPrompt, imgFile)
    setAnswer(answer)
  }

  async function startMic() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const rec = new MediaRecorder(stream)
    mediaRecRef.current = rec
    chunksRef.current = []
    rec.ondataavailable = e => chunksRef.current.push(e.data)
    rec.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      const wav = await blob.arrayBuffer() // backend accepts webm as file; adjust if needed
      const file = new File([wav], 'speech.webm', { type: 'audio/webm' })
      const { text } = await stt(file)
      setQ(text)
    }
    rec.start()
    setRecording(true)
  }

  function stopMic() {
    const rec = mediaRecRef.current
    if (!rec) return
    rec.stop()
    setRecording(false)
  }

  async function speak() {
    const audioBlob = await tts(answer || 'Hello from Friday!')
    const url = URL.createObjectURL(audioBlob)
    const a = new Audio(url)
    a.play()
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24, lineHeight: 1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h1)}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h2)}</pre>

      <h3>Ask (non-stream)</h3>
      <div style={{ display:'flex', gap:8 }}>
        <input style={{ flex:1, padding:8 }} value={q} onChange={e=>setQ(e.target.value)} />
        <button onClick={onAsk}>Ask</button>
        <button onClick={onSSE}>SSE</button>
        <button onClick={onWS}>WebSocket</button>
      </div>

      {answer && (<>
        <h4>Answer</h4>
        <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{answer}</pre>
        <button onClick={speak}>🔊 Speak</button>
      </>)}

      <h3>Vision</h3>
      <input type="file" accept="image/*" onChange={e=>setImgFile(e.target.files[0])} />
      <input style={{ marginLeft:8, padding:8, width:'60%' }} value={imgPrompt} onChange={e=>setImgPrompt(e.target.value)} />
      <button onClick={onVision}>Analyze</button>

      <h3>Mic</h3>
      {!recording
        ? <button onClick={startMic}>🎙️ Start</button>
        : <button onClick={stopMic}>⏹ Stop</button>}
    </div>
  )
}










