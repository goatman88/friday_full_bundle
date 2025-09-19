import React, { useState } from 'react'
import { requestUploadUrl, confirmUpload } from './api'

export default function MultiUploader() {
  const [log, setLog] = useState([])
  const [collection, setCollection] = useState('default')
  const [chunk, setChunk] = useState(800)
  const [overlap, setOverlap] = useState(120)
  const [index, setIndex] = useState('both')
  const [text, setText] = useState('')

  const append = (msg) => setLog((L) => [...L, msg])

  async function uploadText() {
    if (!text.trim()) return
    append('→ getting signed PUT url…')
    const { token, put_url } = await requestUploadUrl()

    append('→ PUT text to storage…')
    const r = await fetch(put_url, { method: 'PUT', body: new Blob([text], { type: 'text/plain' }) })
    if (!r.ok) throw new Error('PUT failed')

    append('→ confirming index…')
    const res = await confirmUpload({
      token, collection, chunk_size: Number(chunk), overlap: Number(overlap), index
    })
    append('✓ indexed: ' + JSON.stringify(res))
  }

  return (
    <section style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8, marginTop: 24 }}>
      <h2>📤 Upload to Friday</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 8 }}>
        <label>Collection<br/><input value={collection} onChange={(e)=>setCollection(e.target.value)} /></label>
        <label>Chunk size<br/><input type='number' value={chunk} onChange={(e)=>setChunk(e.target.value)} /></label>
        <label>Overlap<br/><input type='number' value={overlap} onChange={(e)=>setOverlap(e.target.value)} /></label>
        <label>Index<br/>
          <select value={index} onChange={(e)=>setIndex(e.target.value)}>
            <option value='faiss'>faiss</option>
            <option value='s3'>s3</option>
            <option value='both'>both</option>
          </select>
        </label>
      </div>

      <textarea rows={6} placeholder="Paste any text…" style={{ width: '100%', marginBottom: 8 }}
        value={text} onChange={(e)=>setText(e.target.value)} />
      <button onClick={uploadText}>Upload text</button>

      <pre style={{ background:'#fafafa', padding:8, marginTop:12, maxHeight:180, overflow:'auto' }}>
        {log.join('\n')}
      </pre>
    </section>
  )
}
