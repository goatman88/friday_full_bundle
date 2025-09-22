import React, { useEffect, useState } from 'react'
import { health, apiHealth, ask } from './api.js'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [h1, setH1] = useState('')
  const [h2, setH2] = useState('')
  const [answer, setAnswer] = useState('')
  const [question, setQuestion] = useState('what did the fox do?')

  useEffect(() => {
    (async () => {
      try {
        const r1 = await health()
        const r2 = await apiHealth()
        setH1(JSON.stringify(r1))
        setH2(JSON.stringify(r2))
        setStatus('OK')
      } catch (e) {
        setStatus('ERROR: ' + e.message)
      }
    })()
  }, [])

  async function onAsk() {
    try {
      const data = await ask(question)
      setAnswer(data.answer)
    } catch (e) {
      setAnswer('Query failed: ' + e.message)
    }
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24, lineHeight: 1.35 }}>
      <h1>Friday Frontend</h1>
      <p>Status: <b>{status}</b></p>

      <h3>/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h1)}</pre>

      <h3>/api/health</h3>
      <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(h2)}</pre>

      <h3>Ask (wired to POST /api/ask)</h3>
      <div style={{ display:'flex', gap: 8 }}>
        <input style={{ flex:1, padding:8 }} value={question} onChange={(e) => setQuestion(e.target.value)} />
        <button onClick={onAsk}>Ask</button>
      </div>

      {answer && (
        <>
          <h4>Answer</h4>
          <pre style={{ background:'#111', color:'#0f0', padding:12, overflow:'auto' }}>{String(answer)}</pre>
        </>
      )}
    </div>
  )
}
