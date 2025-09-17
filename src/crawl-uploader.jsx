import React, { useRef, useState } from 'react'

const API = import.meta.env.VITE_API_BASE?.replace(/\/$/, '')

async function jsonFetch(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function CrawlUploader() {
  const fileRef = useRef(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  // Single-file upload flow (presign -> PUT -> confirm)
  const handleUpload = async (e) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return setStatus('Pick a file first.')
    if (!API) return setStatus('VITE_API_BASE is not set.')

    const title = file.name
    const external_id = `file_${Date.now()}`

    try {
      setBusy(true)
      setStatus('Requesting pre-signed URL…')
      const { put_url, s3_uri } = await jsonFetch(`${API}/api/rag/upload_url`, {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      })

      setStatus('Uploading to S3…')
      const putRes = await fetch(put_url, {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        body: file,
      })
      if (!putRes.ok) throw new Error(`PUT failed: ${putRes.status}`)

      setStatus('Confirming upload…')
      await jsonFetch(`${API}/api/rag/confirm_upload`, {
        s3_uri,
        title,
        external_id,
      })

      setStatus('✅ Uploaded and indexed!')
      fileRef.current.value = ''
    } catch (err) {
      console.error(err)
      setStatus(`❌ ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  // Crawl a single URL
  const handleCrawl = async (e) => {
    e.preventDefault()
    if (!API) return setStatus('VITE_API_BASE is not set.')
    const url = new FormData(e.currentTarget).get('url')?.toString().trim()
    if (!url) return setStatus('Enter a URL to crawl.')

    try {
      setBusy(true)
      setStatus('Submitting crawl job…')
      await jsonFetch(`${API}/api/rag/index_url`, { url, external_id: `crawl_${Date.now()}` })
      setStatus('✅ Crawl submitted!')
      e.currentTarget.reset()
    } catch (err) {
      console.error(err)
      setStatus(`❌ ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{padding:24}}>
      <h2>Single File Upload</h2>
      <form onSubmit={handleUpload} style={{display:'grid', gap:12, marginBottom:24}}>
        <input ref={fileRef} type="file" />
        <button disabled={busy} type="submit">Upload & Index</button>
      </form>

      <h2>Crawl a URL</h2>
      <form onSubmit={handleCrawl} style={{display:'grid', gap:12}}>
        <input name="url" type="url" placeholder="https://example.com/page" />
        <button disabled={busy} type="submit">Start Crawl</button>
      </form>

      <p style={{marginTop:16, color:'#555'}}>{status}</p>
      <small style={{display:'block', marginTop:8}}>
        API base: <code>{API || '(missing VITE_API_BASE)'}</code>
      </small>
    </div>
  )
}
