import React, { useMemo, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE?.replace(/\/+$/, '') || ''

/**
 * Assumptions (matches the backend you deployed):
 * 1) POST  /api/rag/file_url
 *    Body: { filename, content_type, external_id }
 *    -> { put_url, s3_url, key }   // put_url is the presigned PUT
 *
 * 2) POST  /api/rag/confirm_upload
 *    Body: { s3_url, filename, title, external_id }
 *    -> { ok: true, job_id }
 *
 * 3) GET   /api/rag/stream/:job_id   (text/event-stream)
 *    -> emits SSE events with {"status": "...", "progress": 0-100}
 */

export default function MultiUploader() {
  const [files, setFiles] = useState([])
  const inputRef = useRef(null)

  const onPick = (e) => {
    const f = Array.from(e.target.files || [])
    if (f.length) {
      // map files to our UI model
      const mapped = f.map(file => ({
        file,
        id: crypto.randomUUID(),
        putProgress: 0,
        sseProgress: 0,
        sseStatus: 'pending',
        jobId: null,
        done: false,
        error: null
      }))
      setFiles(prev => [...prev, ...mapped])
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    const f = Array.from(e.dataTransfer.files || [])
    if (f.length) {
      const mapped = f.map(file => ({
        file,
        id: crypto.randomUUID(),
        putProgress: 0,
        sseProgress: 0,
        sseStatus: 'pending',
        jobId: null,
        done: false,
        error: null
      }))
      setFiles(prev => [...prev, ...mapped])
    }
  }

  const onDragOver = (e) => e.preventDefault()

  const removeItem = (id) => {
    setFiles(prev => prev.filter(x => x.id !== id))
  }

  const humanSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024**2) return `${(bytes/1024).toFixed(1)} KB`
    if (bytes < 1024**3) return `${(bytes/1024**2).toFixed(1)} MB`
    return `${(bytes/1024**3).toFixed(1)} GB`
  }

  const canUpload = useMemo(() => files.some(f => !f.done && !f.error), [files])

  // ——— Core flow per file ———
  const startUpload = async () => {
    for (const item of files) {
      if (item.done || item.error) continue
      try {
        // 1) Get presigned PUT URL
        const ct = item.file.type || 'application/octet-stream'
        const externalId = `ext_${item.id}`
        const r1 = await fetch(`${API_BASE}/api/rag/file_url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: item.file.name,
            content_type: ct,
            external_id: externalId
          })
        })
        if (!r1.ok) throw new Error(`file_url failed: ${r1.status}`)
        const { put_url, s3_url } = await r1.json()

        // 2) PUT file bytes to S3 with progress
        await putWithProgress(put_url, item.file, (pct) => {
          setFiles(prev => prev.map(x => x.id === item.id ? { ...x, putProgress: pct } : x))
        })

        // 3) Confirm upload (this kicks off parsing/indexing)
        const r2 = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            s3_url,
            filename: item.file.name,
            title: item.file.name,
            external_id: externalId
          })
        })
        if (!r2.ok) throw new Error(`confirm_upload failed: ${r2.status}`)
        const { job_id } = await r2.json()

        // 4) Listen to SSE for job status
        await listenSSE(job_id, (msg) => {
          const pct = typeof msg.progress === 'number' ? msg.progress : undefined
          const status = msg.status || '…'
          setFiles(prev => prev.map(x => x.id === item.id
            ? { ...x, jobId: job_id, sseStatus: status, sseProgress: pct ?? x.sseProgress }
            : x
          ))
        })

        // 5) done
        setFiles(prev => prev.map(x => x.id === item.id ? { ...x, done: true, sseStatus: 'done', sseProgress: 100 } : x))
      } catch (err) {
        setFiles(prev => prev.map(x => x.id === item.id ? { ...x, error: String(err) } : x))
      }
    }
  }

  return (
    <main style={{ padding: 24, fontFamily: 'system-ui, sans-serif', lineHeight: 1.35 }}>
      <h1>Multi-file Upload + Progress + Live Status</h1>
      <p style={{ opacity: 0.8, marginTop: 4 }}>
        Backend: <code>{API_BASE || '(missing VITE_API_BASE)'}</code>
      </p>

      <section
        onDrop={onDrop}
        onDragOver={onDragOver}
        style={{
          marginTop: 16,
          padding: 24,
          border: '2px dashed #888',
          borderRadius: 10,
          background: '#fafafa'
        }}>
        <p><b>Drag & drop</b> PDFs/DOCXs/TXTs here, or</p>
        <button onClick={() => inputRef.current?.click()}>Choose files</button>
        <input
          ref={inputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={onPick}
        />
      </section>

      <div style={{ marginTop: 24 }}>
        {files.length === 0 && <div style={{ opacity: 0.7 }}>No files selected yet.</div>}
        {files.map(item => (
          <div key={item.id} style={{
            border: '1px solid #ddd',
            borderRadius: 10,
            padding: 12,
            marginBottom: 12
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div><b>{item.file.name}</b></div>
                <div style={{ fontSize: 12, opacity: 0.75 }}>
                  {item.file.type || 'unknown'} • {humanSize(item.file.size)}
                </div>
              </div>
              <div>
                <button onClick={() => removeItem(item.id)} disabled={!item.error && !item.done}>Remove</button>
              </div>
            </div>

            {/* PUT progress */}
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 4 }}>S3 Upload</div>
              <ProgressBar value={item.putProgress} color="#7c4dff" />
            </div>

            {/* SSE status */}
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 4 }}>
                Parse/Index status: {item.sseStatus}{item.jobId ? ` (job: ${item.jobId})` : ''}
              </div>
              <ProgressBar value={item.sseProgress} color="#2196f3" />
            </div>

            {item.error && (
              <div style={{ marginTop: 10, color: '#b00020', fontSize: 13 }}>
                {item.error}
              </div>
            )}
            {item.done && !item.error && (
              <div style={{ marginTop: 10, color: '#2e7d32', fontSize: 13 }}>
                ✅ Done
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={startUpload} disabled={!canUpload}>Start Uploads</button>
      </div>
    </main>
  )
}

/* ---------- helpers ---------- */

function ProgressBar({ value = 0, color = '#2196f3' }) {
  const pct = Math.max(0, Math.min(100, Math.round(value || 0)))
  return (
    <div style={{
      height: 10,
      background: '#eee',
      borderRadius: 6,
      overflow: 'hidden'
    }}>
      <div style={{
        width: `${pct}%`,
        height: '100%',
        background: color,
        transition: 'width .2s linear'
      }} />
    </div>
  )
}

async function putWithProgress(url, file, onProgress) {
  // Use fetch with ReadableStream to manually report progress
  const total = file.size
  let loaded = 0

  const stream = file.stream()
  const reader = stream.getReader()

  const body = new ReadableStream({
    start(controller) {
      function push() {
        reader.read().then(({ done, value }) => {
          if (done) {
            controller.close()
            return
          }
          loaded += value.byteLength
          onProgress(Math.round((loaded / total) * 100))
          controller.enqueue(value)
          push()
        })
      }
      push()
    }
  })

  const r = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body
  })
  if (!r.ok) throw new Error(`PUT failed: ${r.status}`)
}

async function listenSSE(jobId, onMessage) {
  return new Promise((resolve, reject) => {
    const url = `${API_BASE}/api/rag/stream/${encodeURIComponent(jobId)}`
    const ev = new EventSource(url, { withCredentials: false })

    ev.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessage?.(data)
        if (data.status === 'done' || data.status === 'failed') {
          ev.close()
          if (data.status === 'done') resolve()
          else reject(new Error('job failed'))
        }
      } catch (err) {
        // non-JSON keep-alives are fine to ignore
      }
    }
    ev.onerror = () => {
      ev.close()
      reject(new Error('SSE connection error'))
    }
  })
}
