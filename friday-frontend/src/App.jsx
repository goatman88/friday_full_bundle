import React, { useEffect, useState } from 'react'
import { health } from './api.js'

export default function App() {
  const [status, setStatus] = useState('checking...')
  const [answer, setAnswer] = useState('')
  const [question, setQuestion] = useState('what did the fox do?')

  useEffect(() => {
    health().then(
      () => setStatus('OK'),
      (e) => setStatus('ERROR: ' + e.message)
    )
  }, [])

  async function ask() {
    try {
      const r = await fetch(`${import.meta.env.VITE_API_BASE}/rag/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ top_k: 5, index: 'both', q: question })
      })
      const data = await r.json()
      setAnswer(data.answer ?? JSON.stringify(data))
    } catch (e) {
      setAnswer('Query failed: ' + e.message)
    }
  }

  return (
    <div style={{ maxWidth: 820, margin: '40px auto', fontFamily: 'system-ui, Arial' }}>
      <h1>🚀 Friday Frontend</h1>
      <div style={{ color: status.startsWith('OK') ? 'green' : 'crimson' }}>
        API: {import.meta.env.VITE_API_BASE} — Health: {status}
      </div>

      <hr />

      <label>Ask RAG</label>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button onClick={ask}>Ask</button>
      </div>

      <pre style={{ background: '#f6f6f6', padding: 12, marginTop: 16 }}>
        {answer}
      </pre>
    </div>
  )
}

