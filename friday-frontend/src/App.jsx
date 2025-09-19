import React, { useEffect, useState } from 'react'
import { getHealth, queryRag } from './api'
import MultiUploader from './multi-uploader'

export default function App() {
  const [health, setHealth] = useState('checking…')
  const [q, setQ] = useState('what did the fox do?')
  const [answer, setAnswer] = useState('')

  useEffect(() => {
    getHealth().then((h) => setHealth(h.status || 'ok')).catch((e) => setHealth('error: ' + e.message))
  }, [])

  async function runQuery() {
    const r = await queryRag({ q, top_k: 5, index: 'both' })
    setAnswer(r.answer || JSON.stringify(r))
  }

  return (
    <main style={{ maxWidth: 880, margin: '40px auto', padding: '0 16px', fontFamily:'system-ui,Segoe UI,Arial' }}>
      <h1>🚀 Friday Frontend is Live</h1>
      <p>API base: <code>{import.meta.env.VITE_API_BASE}</code> • Health: <strong>{health}</strong></p>

      <section style={{ border:'1px solid #ddd', padding:16, borderRadius:8 }}>
        <h2>🔎 Quick Query</h2>
        <input value={q} onChange={(e)=>setQ(e.target.value)} style={{ width:'100%', marginBottom:8 }} />
        <button onClick={runQuery}>Ask</button>
        <pre style={{ background:'#fafafa', padding:8, marginTop:8, whiteSpace:'pre-wrap' }}>{answer}</pre>
      </section>

      <MultiUploader />
    </main>
  )
}
