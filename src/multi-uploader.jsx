import React, { useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_BASE?.replace(/\/$/, '')

async function presign(filename, type) {
  const r = await fetch(`${API}/api/rag/upload_url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content_type: type || 'application/octet-stream' }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() // { put_url, s3_uri }
}

async function confirmUpload(payload) {
  const r = await fetch(`${API}/api/rag/confirm_upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function ProgressBar({ value }) {
  return (
    <div style={{height:8, background:'#eee', borderRadius:999, overflow:'hidden'}}>
      <div style={{height:'100%', width:`${value}%`, background:'#4f46e5', transition:'width .2s'}}/>
    </div>
  )
}

export default function MultiUploader() {
  const [picked, setPicked] = useState([])
  const [rows, setRows] = useState([])     // [{name,size,type,progress,status}]
  const [busy, setBusy] = useState(false)

  // metadata form state (shared defaults for the batch)
  const [meta, setMeta] = useState({
    collection: 'default',
    tags: 'batch, uploads',
    source: 'multi-upload',
    author: '',
    chunk_size: 1200,
    chunk_overlap: 150,
  })

  const metaPrepared = useMemo(() => ({
    collection: meta.collection || undefined,
    source: meta.source || undefined,
    author: meta.author || undefined,
    tags: meta.tags.split(',').map(t => t.trim()).filter(Boolean),
    chunk_size: Number(meta.chunk_size || 1200),
    chunk_overlap: Number(meta.chunk_overlap || 150),
  }), [meta])

  const handlePick = (e) => {
    const files = Array.from(e.target.files || [])
    setPicked(files)
    setRows(files.map(f => ({ name: f.name, size: f.size, type: f.type || 'application/octet-stream', progress: 0, status: 'queued', file: f })))
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files || [])
    setPicked(files)
    setRows(files.map(f => ({ name: f.name, size: f.size, type: f.type || 'application/octet-stream', progress: 0, status: 'queued', file: f })))
  }

  const uploadAll = async () => {
    if (!API) return alert('VITE_API_BASE is not set.')
    if (!rows.length) return alert('Pick files first.')
    setBusy(true)

    // helper to update a row by index
    const patch = (i, changes) =>
      setRows(prev => prev.map((r, idx) => idx === i ? { ...r, ...changes } : r))

    for (let i = 0; i < rows.length; i++) {
      const { file } = rows[i]
      try {
        patch(i, { status: 'presigning…', progress: 0 })
        const { put_url, s3_uri } = await presign(file.name, file.type)

        // PUT to S3 with progress
        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest()
          xhr.open('PUT', put_url)
          xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')
          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable) {
              const pct = Math.round((ev.loaded / ev.total) * 100)
              patch(i, { progress: pct, status: `uploading ${pct}%` })
            }
          }
          xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`PUT ${xhr.status}`))
          xhr.onerror = () => reject(new Error('PUT network error'))
          xhr.send(file)
        })

        patch(i, { status: 'confirming…' })
        await confirmUpload({
          s3_uri,
          title: file.name,
          external_id: `batch_${Date.now()}_${i}`,
          metadata: metaPrepared,
          chunk: { size: metaPrepared.chunk_size, overlap: metaPrepared.chunk_overlap },
        })

        patch(i, { status: '✅ done', progress: 100 })
      } catch (err) {
        console.error(err)
        patch(i, { status: `❌ ${err.message}` })
      }
    }

    setBusy(false)
  }

  const box = { padding:24, border:'2px dashed #bbb', borderRadius:8, marginBottom:12 }

  return (
    <div style={{padding:24}}>
      <h2>Multi Upload (progress + metadata)</h2>

      <div onDragOver={(e)=>e.preventDefault()} onDrop={handleDrop} style={box}>
        Drag & drop files here
      </div>

      <input type="file" multiple onChange={handlePick} style={{marginBottom:16}} />

      <fieldset style={{border:'1px solid #eee', borderRadius:8, padding:16, marginBottom:16}}>
        <legend>Metadata for all files</legend>
        <div style={{display:'grid', gap:12, gridTemplateColumns:'1fr 1fr'}}>
          <label>Collection
            <input value={meta.collection} onChange={e=>setMeta(m=>({...m, collection:e.target.value}))} />
          </label>
          <label>Tags (comma separated)
            <input value={meta.tags} onChange={e=>setMeta(m=>({...m, tags:e.target.value}))} />
          </label>
          <label>Source
            <input value={meta.source} onChange={e=>setMeta(m=>({...m, source:e.target.value}))} />
          </label>
          <label>Author
            <input value={meta.author} onChange={e=>setMeta(m=>({...m, author:e.target.value}))} />
          </label>
          <label>Chunk size
            <input type="number" value={meta.chunk_size} onChange={e=>setMeta(m=>({...m, chunk_size:e.target.value}))} />
          </label>
          <label>Chunk overlap
            <input type="number" value={meta.chunk_overlap} onChange={e=>setMeta(m=>({...m, chunk_overlap:e.target.value}))} />
          </label>
        </div>
      </fieldset>

      <button disabled={busy || !rows.length} onClick={uploadAll}>Upload All</button>

      {!!rows.length && (
        <div style={{marginTop:16, display:'grid', gap:10}}>
          {rows.map((r, i) => (
            <div key={r.name + i} style={{border:'1px solid #eee', borderRadius:8, padding:12}}>
              <div style={{display:'flex', justifyContent:'space-between', marginBottom:8}}>
                <strong style={{overflow:'hidden', textOverflow:'ellipsis'}}>{r.name}</strong>
                <span style={{fontSize:12, color:'#555'}}>{r.status}</span>
              </div>
              <ProgressBar value={r.progress} />
            </div>
          ))}
        </div>
      )}

      <small style={{display:'block', marginTop:16}}>
        API base: <code>{API || '(missing VITE_API_BASE)'}</code>
      </small>
    </div>
  )
}

