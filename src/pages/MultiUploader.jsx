import React, { useCallback, useMemo, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE?.replace(/\/+$/,"") || "http://127.0.0.1:8000";

async function postJSON(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`POST ${path} ${res.status}: ${txt}`);
  }
  return res.json();
}

function prettyBytes(n) {
  if (n == null || isNaN(n)) return "-";
  const units = ["B","KB","MB","GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

export default function MultiUploader() {
  const [items, setItems] = useState([]);  // [{file, id, status, pct, s3Uri, putUrl, error}]
  const [uploading, setUploading] = useState(false);
  const dropRef = useRef(null);

  const accept = useMemo(() => ([
    ".pdf",".docx",".txt",".md",".csv",".json",".pptx",".xlsx",".html"
  ]), []);

  const onPick = useCallback((filesList) => {
    const files = Array.from(filesList || []);
    if (!files.length) return;
    const rows = files.map((f, idx) => ({
      id: `${Date.now()}_${idx}_${f.name}`,
      file: f,
      status: "queued",
      pct: 0,
      s3Uri: null,
      putUrl: null,
      error: null,
    }));
    setItems(prev => [...prev, ...rows]);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    onPick(e.dataTransfer.files);
  }, [onPick]);

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropRef.current) dropRef.current.dataset.active = "1";
  };
  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (dropRef.current) delete dropRef.current.dataset.active;
  };

  const removeItem = (id) => setItems(prev => prev.filter(r => r.id !== id));
  const reset = () => setItems([]);

  async function uploadOne(row) {
    const file = row.file;
    const contentType = file.type || "application/octet-stream";

    // 1) Ask backend for presigned PUT URL
    const presign = await postJSON("/api/rag/file_url", {
      filename: file.name,
      content_type: contentType,
    });
    // expected: { put_url, s3_uri }
    if (!presign?.put_url || !presign?.s3_uri) {
      throw new Error(`Bad presign response: ${JSON.stringify(presign)}`);
    }

    // 2) PUT file → S3 (stream progress)
    const putUrl = presign.put_url;
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", putUrl);
      xhr.setRequestHeader("Content-Type", contentType);
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          const pct = Math.round((evt.loaded / evt.total) * 100);
          setItems(prev => prev.map(r => r.id === row.id ? { ...r, pct, status: "uploading" } : r));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`S3 PUT failed: ${xhr.status} ${xhr.responseText || ""}`));
        }
      };
      xhr.onerror = () => reject(new Error("S3 PUT network error"));
      xhr.send(file);
    });

    // 3) Confirm upload so backend can parse/index
    const confirm = await postJSON("/api/rag/confirm_upload", {
      s3_uri: presign.s3_uri,
      title: file.name,
      external_id: row.id,
      // Optional: inline content for tiny .txt; big docs will be parsed from S3
      content: undefined,
    });

    setItems(prev => prev.map(r =>
      r.id === row.id ? { ...r, pct: 100, status: "done", s3Uri: presign.s3_uri, putUrl: presign.put_url } : r
    ));
    return confirm;
  }

  const startAll = async () => {
    if (!items.length) return;
    setUploading(true);
    try {
      // run sequentially (simpler to read logs). Flip to Promise.all for parallel.
      for (const row of items) {
        try {
          await uploadOne(row);
        } catch (err) {
          setItems(prev => prev.map(r =>
            r.id === row.id ? { ...r, status: "error", error: String(err) } : r
          ));
        }
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{maxWidth: 900, margin: "40px auto", padding: "0 16px", fontFamily: "system-ui, sans-serif"}}>
      <h1 style={{marginBottom: 8}}>Multi Uploader</h1>
      <p style={{marginTop: 0, color: "#555"}}>
        Drag files here or click the button. We’ll presign → PUT to S3 → confirm with the backend.
      </p>

      <div
        ref={dropRef}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        style={{
          border: "2px dashed #888",
          borderRadius: 12,
          padding: 28,
          textAlign: "center",
          marginBottom: 16,
          background: dropRef.current?.dataset.active ? "#f5faff" : "transparent",
        }}
      >
        <input
          id="picker"
          type="file"
          multiple
          accept={accept.join(",")}
          onChange={(e) => onPick(e.target.files)}
          style={{ display: "none" }}
        />
        <div style={{marginBottom: 8}}>Drop files here</div>
        <button onClick={() => document.getElementById("picker").click()}>
          Choose files
        </button>
        <div style={{marginTop: 8, fontSize: 12, color: "#777"}}>
          Allowed: {accept.join(" ")}
        </div>
      </div>

      <div style={{display: "flex", gap: 8, marginBottom: 16}}>
        <button onClick={startAll} disabled={!items.length || uploading}>Start upload</button>
        <button onClick={reset} disabled={!items.length || uploading}>Clear</button>
      </div>

      {!items.length ? (
        <div style={{color: "#777"}}>No files selected yet.</div>
      ) : (
        <ul style={{listStyle:"none", padding: 0, margin: 0, display: "grid", gap: 12}}>
          {items.map(row => (
            <li key={row.id} style={{border: "1px solid #ddd", borderRadius: 10, padding: 12}}>
              <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", gap: 12}}>
                <div style={{fontWeight: 600}}>{row.file.name}</div>
                <div style={{fontSize:12, color:"#666"}}>
                  {prettyBytes(row.file.size)} · {row.file.type || "application/octet-stream"}
                </div>
              </div>

              <div style={{marginTop: 8, height: 8, background:"#eee", borderRadius: 999}}>
                <div
                  style={{
                    width: `${row.pct}%`,
                    height: "100%",
                    background: row.status === "error" ? "#e11d48" : "#3b82f6",
                    borderRadius: 999,
                    transition: "width .2s",
                  }}
                />
              </div>

              <div style={{display:"flex", justifyContent:"space-between", marginTop: 8, fontSize: 12}}>
                <div>
                  Status: <b>{row.status}</b>
                  {row.status === "uploading" || row.status === "done" ? ` · ${row.pct}%` : ""}
                </div>
                <div style={{display:"flex", gap: 8}}>
                  {row.s3Uri ? <code title="S3 URI">{row.s3Uri}</code> : null}
                </div>
              </div>

              {row.error ? (
                <div style={{marginTop: 8, color:"#b91c1c", fontSize: 12, whiteSpace:"pre-wrap"}}>
                  {row.error}
                </div>
              ) : null}

              <div style={{marginTop: 8, display:"flex", gap: 8}}>
                <button onClick={() => removeItem(row.id)} disabled={uploading}>Remove</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

