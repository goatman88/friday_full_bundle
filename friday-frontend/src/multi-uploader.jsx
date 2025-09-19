import React, { useState } from 'react'
import { getUploadUrl, confirmUpload } from './api'

export default function MultiUploader() {
  const [text, setText] = useState('')
  const [collection, setCollection] = useState('default')
  const [index, setIndex] = useState('both')   // 'faiss' | 's3' | 'both'
  const [chunkSize, setChunkSize] = useState(800)
  const [overlap, setOverlap] = useState(120)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState(null)
  const [file, setFile] = useState(null)

  async function putBytes(put_url, bytes, contentType) {
    const r = await fetch(put_url, { method: 'PUT', body: bytes, headers: { 'Content-Type': contentType }})
    if (!r.ok) throw new Error('PUT failed')
  }

  async function doUpload(bytes, contentType) {
    setBusy(true)
    try {
      const { token, put_url } = await getUploadUrl()
      await putBytes(put_url, bytes, contentType)
      const res = await confirmUpload({ token, collection, chunk_size: chunkSize, overlap, index })
      setLast(res)
    } catch (e) {
      setLast({ error: String(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{padding:'1rem', border:'1px solid #ddd', borderRadius:8}}>
      <h3 style={{marginTop:0}}>Upload to Friday</h3>

      <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:12}}>
        <label>Collection<br/>
          <input value={collection} onChange={e=>setCollection(e.target.value)} />
        </label>
        <label>Index<br/>
          <select value={index} onChange={e=>setIndex(e.target.value)}>
            <option value="faiss">faiss</option>
            <option value="s3">s3</option>
            <option value="both">both</option>
          </select>
        </label>
        <label>Chunk size<br/>
          <input type="number" value={chunkSize} onChange={e=>setChunkSize(+e.target.value)} />
        </label>
        <label>Overlap<br/>
          <input type="number" value={overlap} onChange={e=>setOverlap(+e.target.value)} />
        </label>
      </div>

      <textarea
        placeholder="Paste any text to index…"
        rows={6}
        style={{width:'100%', marginBottom:8}}
        value={text}
        onChange={e=>setText(e.target.value)}
      />
      <div style={{display:'flex', gap:8, marginBottom:12}}>
        <button disabled={busy || !text.trim()} onClick={() => {
          const bytes = new TextEncoder().encode(text)
          doUpload(bytes, 'text/plain')
        }}>
          {busy ? 'Uploading…' : 'Upload text'}
        </button>

        <input type="file" onChange={e=>setFile(e.target.files?.[0] ?? null)} />
        <button disabled={busy || !file} onClick={async ()=>{
          const bytes = new Uint8Array(await file.arrayBuffer())
          await doUpload(bytes, file.type || 'application/octet-stream')
        }}>
          {busy ? 'Uploading…' : 'Upload file'}
        </button>
      </div>

      {last && <pre style={{background:'#f6f6f6', padding:12, borderRadius:6, overflow:'auto'}}>{JSON.stringify(last, null, 2)}</pre>}
    </div>
  )
}
