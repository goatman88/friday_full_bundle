import React, { useRef, useState } from 'react'

const API = import.meta.env.VITE_API_BASE?.replace(/\/$/, '')

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function CrawlUploader() {
  const fileRef = useRef(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  // single-file upload with metadata
  const onUpload = async (e) => {
    e.preventDefault()
    if (!API) return setMsg('VITE_API_BASE missing.')
    const file = fileRef.current?.files?.[0]
    if (!file) return setMsg('Pick a file.')

    const fd = new FormData(e.currentTarget)
    const meta = {
      collection: fd.get('collection')?.trim() || undefined,
      source: fd.get('source')?.trim() || undefined,
      author: fd.get('author')?.trim() || undefined,
      tags: fd.get('tags')?.split(',').map(t => t.trim()).filter(Boolean) || [],
      chunk_size: Number(fd.get('chunk_size') || 1200),
      chunk_overlap: Number(fd.get('chunk_overlap') || 150),
    }

    try {
      setBusy(true); setMsg('Requesting pre-signed URL…')
      const { put_url, s3_uri } = await postJSON(`${API}/api/rag/upload_url`, {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      })

      // upload with progress (XHR)
      setMsg('Uploading to S3…')
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('PUT', put_url)
        xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100)
            setMsg(`Uploading… ${pct}%`)
          }
        }
        xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`PUT ${xhr.status}`))
        xhr.onerror = () => reject(new Error('PUT network error'))
        xhr.send(file)
      })

      setMsg('Confirming upload…')
      await postJSON(`${API}/api/rag/confirm_upload`, {
        s3_uri,
        title: file.name,
        external_id: `file_${Date.now()}`,
        metadata: meta,
        chunk: { size: meta.chunk_size, overlap: meta.chunk_overlap },
      })

      setMsg('✅ Uploaded and indexed')
      e.currentTarget.reset()
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      console.error(err)
      setMsg(`❌ ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  // crawl with metadata
  const onCrawl = async (e) => {
    e.preventDefault()
    if (!API) return setMsg('VITE_API_BASE missing.')
    const fd = new FormData(e.currentTarget)
    const url = fd.get('url')?.toString().trim()
    if (!url) return setMsg('Enter a URL to crawl.')

    const meta = {
      collection: fd.get('collection')?.trim() || undefined,
      source: fd.get('source')?.trim() || 'crawl',
      author: fd.get('author')?.trim() || undefined,
      tags: fd.get('tags')?.split(',').map(t => t.trim()).filter(Boolean) || [],
      chunk_size: Number(fd.get('chunk_size') || 1200),
      chunk_overlap: Number(fd.get('chunk_overlap') || 150),
    }

    try {
      setBusy(true); setMsg('Submitting crawl…')
      await postJSON(`${API}/api/rag/index_url`, {
        url,
        external_id: `crawl_${Date.now()}`,
        metadata: meta,
        chunk: { size: meta.chunk_size, overlap: meta.chunk_overlap },
      })
      setMsg('✅ Crawl submitted')
      e.currentTarget.reset()
    } catch (err) {
      console.error(err)
      setMsg(`❌ ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  const Field = ({label, children}) => (
    <label style={{display:'grid', gap:6}}>
      <span style={{fontSize:12, color:'#444'}}>{label}</span>
      {children}
    </label>
  )

  return (
    <div style={{padding:24}}>
      <h2>Single File Upload (with metadata)</h2>
      <form onSubmit={onUpload} style={{display:'grid', gap:12, marginBottom:24, maxWidth:640}}>
        <input ref={fileRef} type="file" />
        <Field label="Collection"><input name="collection" placeholder="default"/></Field>
        <Field label="Tags (comma separated)"><input name="tags" placeholder="invoices, 2024, west"/></Field>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
          <Field label="Source"><input name="source" placeholder="manual-upload"/></Field>
          <Field label="Author"><input name="author" placeholder="Michael"/></Field>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
          <Field label="Chunk size"><input name="chunk_size" type="number" defaultValue={1200}/></Field>
          <Field label="Chunk overlap"><input name="chunk_overlap" type="number" defaultValue={150}/></Field>
        </div>
        <button disabled={busy} type="submit">Upload & Index</button>
      </form>

      <h2>Crawl a URL (with metadata)</h2>
      <form onSubmit={onCrawl} style={{display:'grid', gap:12, maxWidth:640}}>
        <Field label="URL to crawl"><input name="url" type="url" placeholder="https://example.com/page"/></Field>
        <Field label="Collection"><input name="collection" placeholder="default"/></Field>
        <Field label="Tags (comma separated)"><input name="tags" placeholder="docs, site, public"/></Field>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
          <Field label="Source"><input name="source" placeholder="web-crawl"/></Field>
          <Field label="Author"><input name="author" placeholder="Site owner"/></Field>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
          <Field label="Chunk size"><input name="chunk_size" type="number" defaultValue={1200}/></Field>
          <Field label="Chunk overlap"><input name="chunk_overlap" type="number" defaultValue={150}/></Field>
        </div>
        <button disabled={busy} type="submit">Submit Crawl</button>
      </form>

      <p style={{marginTop:16}}>{msg}</p>
      <small>API: <code>{API || '(missing VITE_API_BASE)'}</code></small>
    </div>
  )
}


