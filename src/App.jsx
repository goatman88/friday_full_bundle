import React, { useEffect, useState } from 'react'
import { health, apiHealth, ask } from './api.js'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [h1, setH1] = useState('')
  const [h2, setH2] = useState('')
  const [question, setQuestion] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')

  useEffect(() => {
    Promise.allSettled([health(), apiHealth()])
      .then(([a,b]) => {
        setH1(JSON.stringify(a.value ?? a.reason?.message ?? 'error'))
        setH2(JSON.stringify(b.value ?? b.reason?.message ?? 'error'))
        if (a.status === 'fulfilled' && b.status === 'fulfilled') setStatus('OK')
        else setStatus('ERROR')
      })
      .catch(e => setStatus('ERROR: ' + e.message))
  }, [])

  async function onAsk() {
    try {
      const data = await ask(question)
      setAnswer(JSON.stringify(data))
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
        <input style={{ flex:1, padding:8 }} value={question} onChange={e => setQuestion(e.target.value)} />
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









