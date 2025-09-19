import React, { useEffect, useState } from 'react'
import { health, queryRag } from './api'
import MultiUploader from './multi-uploader.jsx'

export default function App() {
  const [h, setH] = useState(null)
  const [q, setQ] = useState('what did the fox do?')
  const [ans, setAns] = useState(null)

  useEffect(() => { health().then(setH).catch(e=>setH({error:String(e)})) }, [])

  return (
    <div style={{maxWidth:900, margin:'32px auto', fontFamily:'system-ui, Arial'}}>
      <h1>🚀 Friday Frontend</h1>
      <p style={{opacity:.8, marginTop:-8}}>
        API: {import.meta.env.VITE_API_BASE || '(unset)'} · Health: {h ? JSON.stringify(h) : '…'}
      </p>

      <MultiUploader />

      <div style={{marginTop:24, padding:16, border:'1px solid #ddd', borderRadius:8}}>
        <h3 style={{marginTop:0}}>Ask RAG</h3>
        <div style={{display:'flex', gap:8}}>
          <input style={{flex:1}} value={q} onChange={e=>setQ(e.target.value)} />
          <button onClick={async()=> setAns(await queryRag(q, 5, 'both'))}>Ask</button>
        </div>
        {ans && <pre style={{background:'#f6f6f6', padding:12, borderRadius:6, overflow:'auto', marginTop:12}}>
          {JSON.stringify(ans, null, 2)}
        </pre>}
      </div>
    </div>
  )
}
