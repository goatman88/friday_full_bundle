import React, { useEffect, useRef, useState } from 'react'
import { health, apiHealth, ask, askStream, wsChat, vision, stt, tts } from './api.js'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [h1, setH1] = useState(''); const [h2, setH2] = useState('')

  const [question, setQuestion] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')

  const [streaming, setStreaming] = useState(false)
  const [mode, setMode] = useState('SSE') // SSE | WS

  const [prompt, setPrompt] = useState('Describe this image')
  const [imageUrl, setImageUrl] = useState('')
  const [file, setFile] = useState(null)
  const fileRef = useRef(null)

  // camera
  const videoRef = useRef(null)
  const [camOn, setCamOn] = useState(false)

  // mic
  const [sttText, setSttText] = useState('')
  const [rec, setRec] = useState(null)
  const [recording, setRecording] = useState(false)

  useEffect(() => {
    Promise.all([health(), apiHealth()])
      .then(([a,b]) => { setH1(JSON.stringify(a)); setH2(JSON.stringify(b)); setStatus('OK') })
      .catch(() => setStatus('ERROR'))
  }, [])

  function playWav(b64) { new Audio('data:audio/wav;base64,' + b64).play().catch(()=>{}) }

  async function onAsk() {
    setStreaming(false)
    const data = await ask(question)
    setAnswer(data.answer)
    playWav(await tts(data.answer))
  }

  function onAskStream() {
    setAnswer(''); setStreaming(true)
    const stop = (mode === 'SSE')
      ? askStream({ q: question, onToken: t => setAnswer(a => a + t), onDone: () => setStreaming(false), onError: () => setStreaming(false) })
      : wsChat({ q: question, onToken: t => setAnswer(a => a + t), onDone: () => setStreaming(false), onError: () => setStreaming(false) })
    return stop
  }

  async function onVision() {
    const data = await vision({ prompt, imageUrl, file })
    setAnswer(data.answer)
  }

  async function startRec() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio:true })
    const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    const chunks = []
    mr.ondataavailable = e => chunks.push(e.data)
    mr.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const data = await stt(blob)
      setSttText(data.text || '')
    }
    mr.start(); setRec(mr); setRecording(true)
  }
  function stopRec(){ rec?.stop(); setRecording(false) }

  async function toggleCam(){
    if (!camOn){
      const stream = await navigator.mediaDevices.getUserMedia({ video:true })
      videoRef.current.srcObject = stream; await videoRef.current.play(); setCamOn(true)
    } else {
      const t = videoRef.current.srcObject; t.getTracks().forEach(x=>x.stop()); videoRef.current.srcObject=null; setCamOn(false)
    }
  }
  function snap(){
    const v = videoRef.current; if (!v) return
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    const ctx = c.getContext('2d'); ctx.drawImage(v,0,0)
    c.toBlob(b => setFile(new File([b],'snap.png',{type:'image/png'})), 'image/png')
  }

  return (
    <div style={{fontFamily:'system-ui, sans-serif', padding:24, lineHeight:1.35}}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{background:'#111',color:'#0f0',padding:12,overflow:'auto'}}>{h1}</pre>

      <h3>/api/health</h3>
      <pre style={{background:'#111',color:'#0f0',padding:12,overflow:'auto'}}>{h2}</pre>

      <h3 style={{margin:'24px 0'}}>Ask</h3>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        <input style={{flex:1,padding:8}} value={question} onChange={e=>setQuestion(e.target.value)} />
        <button onClick={onAsk}>Ask</button>
        <select value={mode} onChange={e=>setMode(e.target.value)}>
          <option>SSE</option><option>WS</option>
        </select>
        <button onClick={onAskStream} disabled={streaming}>{streaming ? 'Streaming...' : 'Stream'}</button>
      </div>

      <h3 style={{margin:'24px 0'}}>Vision</h3>
      <div style={{display:'grid',gap:8,gridTemplateColumns:'1fr auto'}}>
        <input placeholder="Prompt" value={prompt} onChange={e=>setPrompt(e.target.value)} />
        <div/>
        <input placeholder="Image URL" value={imageUrl} onChange={e=>setImageUrl(e.target.value)} />
        <button onClick={()=>fileRef.current?.click()}>Upload</button>
        <input ref={fileRef} type="file" accept="image/*" style={{display:'none'}} onChange={e=>setFile(e.target.files?.[0]||null)} />
        <button onClick={onVision}>Describe</button>
      </div>

      <h4 style={{marginTop:16}}>Camera</h4>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        <button onClick={toggleCam}>{camOn?'Stop Cam':'Start Cam'}</button>
        <button onClick={snap} disabled={!camOn}>📸 Snapshot</button>
        <video ref={videoRef} style={{width:220,height:150,background:'#222'}} />
      </div>

      <h3 style={{margin:'24px 0'}}>Speech</h3>
      <div style={{display:'flex',gap:8}}>
        {!recording ? <button onClick={startRec}>🎙️ Record</button> : <button onClick={stopRec}>⏹ Stop</button>}
        <input style={{flex:1,padding:8}} value={sttText} onChange={e=>setSttText(e.target.value)} />
        <button onClick={async()=>playWav(await tts(sttText||'Hello'))}>🔊 Speak</button>
      </div>

      {answer && (<div style={{marginTop:24}}>
        <h4>Answer</h4>
        <pre style={{background:'#111',color:'#0f0',padding:12,overflow:'auto',whiteSpace:'pre-wrap'}}>{answer}</pre>
      </div>)}
    </div>
  )
}








