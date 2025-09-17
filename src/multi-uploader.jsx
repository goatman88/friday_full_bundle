import React, { useState } from 'react'
const API = import.meta.env.VITE_API_BASE?.replace(/\/$/, '')

async function presign(name, type) {
  const r = await fetch(`${API}/api/rag/upload_url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: name, content_type: type || 'application/octet-stream' }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json() // { put_url, s3_uri }
}

export default function MultiUploader() {
  const [files, setFiles] = useState([])
  const [log, setLog] = useState([])
  const [busy, setBusy] = useState(false)

  const push = (msg) => setLog((l) => [...l, msg])

  const onPick = (e) => setFiles(Array.from(e.target.files || []))

  const onDrop = (e) => {
    e.preventDefault()
    setFiles(Array.from(e.dataTransfer.files || []))
  }

  const uploadAll = async () => {
    if (!API) return push('VITE_API_BASE is not set.')
    if (!files.length) return push('Pick some files first.')
    setBusy(true)
    setLog([])

    for (const f of files) {
      try {
        push(`Presign: ${f.name}`)
        const { put_url, s3_uri } = await presign(f.name, f.type)

        push(`PUT → S3: ${f.name}`)
        const put = await fetch(put_url, { method: 'PUT', headers: { 'Content-Type': f.type || 'application/octet-stream' }, body: f })
        if (!put.ok) throw new Error(`PUT failed ${put.status}`)

        push(`Confirm: ${f.name}`)
        const r = await fetch(`${API}/api/rag/confirm_upload`, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ s3_uri, title: f.name, external_id: `batch_${Date.now()}_${f.name}` })
        })
        if (!r.ok) throw new Error(await r.text())

        push(`✅ Done: ${f.name}`)
      } catch (err) {
        push(`❌ ${f.name}: ${err.message}`)
      }
    }

    setBusy(false)
  }

  return (
    <div style={{padding:24}}>
      <h2>Multi Upload</h2>
      <div onDragOver={(e)=>e.preventDefault()} onDrop={onDrop}
           style={{padding:24, border:'2px dashed #bbb', borderRadius:8, marginBottom:12}}>
        Drag & drop files here
      </div>
      <input type="file" multiple onChange={onPick} />
      <div style={{marginTop:12}}>
        <button disabled={busy} onClick={uploadAll}>Upload All</button>
      </div>
      {!!files.length && (
        <ul style={{marginTop:12}}>
          {files.map(f => <li key={f.name}>{f.name} ({f.type || 'application/octet-stream'})</li>)}
        </ul>
      )}
      <pre style={{marginTop:16, padding:12, background:'#f7f7f7', borderRadius:6, whiteSpace:'pre-wrap'}}>
        {log.join('\n') || 'Logs will appear here…'}
      </pre>
      <small>API base: <code>{API || '(missing VITE_API_BASE)'}</code></small>
    </div>
  )
}
