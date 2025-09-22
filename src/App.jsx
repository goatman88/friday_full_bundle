import React, { useEffect, useRef, useState } from 'react'
import { health, apiHealth, ask, vision, stt, tts } from './api.js'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [h1, setH1] = useState('')
  const [h2, setH2] = useState('')

  const [question, setQuestion] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')

  const [prompt, setPrompt] = useState('Describe this image')
  const [imageUrl, setImageUrl] = useState('')
  const [file, setFile] = useState(null)
  const fileRef = useRef(null)

  const [sttText, setSttText] = useState('')
  const [rec, setRec] = useState(null)
  const [recording, setRecording] = useState(false)

  useEffect(() => {
    Promise.all([health(), apiHealth()])
      .then(([a, b]) => {
        setH1(JSON.stringify(a))
        setH2(JSON.stringify(b))
        setStatus('OK')
      })
      .catch(() => setStatus('ERROR'))
  }, [])

  async function onAsk() {
    try {
      const data = await ask(question)
      setAnswer(data.answer)
      const wav = await tts(data.answer)
      playWav(wav)
    } catch (e) {
      setAnswer(String(e.message || e))
    }
  }

  async function onVision() {
    try {
      const data = await vision({ prompt, imageUrl, file })
      setAnswer(data.answer)
    } catch (e) {
      setAnswer(String(e.message || e))
    }
  }

  async function startRec() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    const chunks = []
    mediaRecorder.ondataavailable = e => chunks.push(e.data)
    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const data = await stt(blob)
      setSttText(data.text || '')
    }
    mediaRecorder.start()
    setRec(mediaRecorder)
    setRecording(true)
  }

  function stopRec() {
    if (rec) {
      rec.stop()
      setRecording(false)
    }
  }

  function playWav(b64) {
    const audio = new Audio('data:audio/wav;base64,' + b64)
    audio.play().catch(() => {})
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24, lineHeight: 1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h1)}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h2)}</pre>

      <h3 style={{margin:'24px 0'}}>Ask (LLM + optional TTS)</h3>
      <div style={{ display:'flex', gap:8 }}>
        <input style={{ flex:1, padding:8 }} value={question} onChange={e => setQuestion(e.target.value)} />
        <button onClick={onAsk}>Ask</button>
      </div>

      <h3 style={{margin:'24px 0'}}>Vision</h3>
      <div style={{ display:'grid', gap:8, gridTemplateColumns: '1fr auto' }}>
        <input placeholder="Prompt" value={prompt} onChange={e => setPrompt(e.target.value)} />
        <div />
        <input placeholder="Image URL" value={imageUrl} onChange={e => setImageUrl(e.target.value)} />
        <button onClick={() => fileRef.current?.click()}>Upload</button>
        <input ref={fileRef} type="file" accept="image/*" style={{ display:'none' }} onChange={e => setFile(e.target.files?.[0] || null)} />
        <button onClick={onVision}>Describe</button>
      </div>

      <h3 style={{margin:'24px 0'}}>Speech</h3>
      <div style={{ display:'flex', gap:8 }}>
        {!recording ? <button onClick={startRec}>🎙️ Record</button> : <button onClick={stopRec}>⏹ Stop</button>}
        <input style={{ flex:1, padding:8 }} value={sttText} onChange={e => setSttText(e.target.value)} />
        <button onClick={async () => playWav(await tts(sttText || 'Hello!'))}>🔊 Speak</button>
      </div>

      {answer && (
        <div style={{marginTop:24}}>
          <h4>Answer</h4>
          <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(answer)}</pre>
        </div>
      )}
    </div>
  )
}







