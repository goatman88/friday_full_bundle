import React, { useCallback, useMemo, useRef, useState } from "react";
import API_BASE from "../lib/apiBase";
import { useSSEJob, JobUpdate } from "../hooks/useSSEJob";

type FileState = {
  id: string;                 // external_id also used as job_id
  file: File;
  putProgress: number;        // PUT to S3 progress 0..100
  jobStatus?: string;         // queued | processing | done | error
  jobProgress?: number;       // 0..100 (server-reported)
  message?: string;
  stage: "queued" | "signing" | "uploading" | "confirming" | "processing" | "done" | "error";
  downloadUrl?: string;
};

function putWithProgress(url: string, file: File, contentType: string, onProgress: (pct: number) => void) {
  return new Promise<Response>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Type", contentType || "application/octet-stream");
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable) onProgress(Math.round((evt.loaded / evt.total) * 100));
    };
    xhr.onload = () => {
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (!ok) return reject(new Error(`S3 PUT failed: ${xhr.status} ${xhr.responseText || ""}`));
      resolve(new Response(xhr.responseText, { status: xhr.status }));
    };
    xhr.onerror = () => reject(new Error("Network error during S3 PUT"));
    xhr.send(file);
  });
}

export default function MultiUploaderWithStatus() {
  const [items, setItems] = useState<FileState[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const canStart = useMemo(() => items.some(i => i.stage === "queued" || i.stage === "error"), [items]);

  const addFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const next = Array.from(list).map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      putProgress: 0,
      stage: "queued" as const
    }));
    setItems(prev => [...prev, ...next]);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  function patch(id: string, p: Partial<FileState>) {
    setItems(prev => prev.map(it => it.id === id ? { ...it, ...p } : it));
  }

  async function processOne(it: FileState) {
    const { file, id } = it;
    const contentType = file.type || "application/octet-stream";

    patch(id, { stage: "signing", message: "Presigning…" });
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_type: contentType })
    }).then(r => r.json()).catch(e => ({ ok: false, error: String(e) }));

    if (!ask?.ok || !ask.url || !ask.s3_uri) {
      patch(id, { stage: "error", message: "Presign failed: " + (ask?.error || "unknown") });
      return;
    }

    patch(id, { stage: "uploading", message: "Uploading to S3…", putProgress: 0 });
    try {
      await putWithProgress(ask.url, file, contentType, (pct) => patch(id, { putProgress: pct }));
    } catch (err: any) {
      patch(id, { stage: "error", message: err?.message || "Upload failed" });
      return;
    }

    patch(id, { stage: "confirming", message: "Confirming…" });
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri: ask.s3_uri, title: file.name, external_id: id })
    }).then(r => r.json()).catch(e => ({ ok: false, error: String(e) }));

    if (!confirm?.ok) {
      patch(id, { stage: "error", message: "Confirm failed: " + (confirm?.error || "unknown") });
      return;
    }

    // Start SSE if supported; else fallback to polling
    const { start, stop, supported } = useSSEJobInstance(id, (u) => {
      if (u.ok && u.job) {
        patch(id, {
          jobStatus: u.job.status,
          jobProgress: u.job.progress,
          message: u.job.message,
          stage: u.job.status === "done" ? "done" : (u.job.status === "error" ? "error" : "processing")
        });
      }
    });

    if (supported) {
      start();
      // stop is called automatically when job ends inside the handler
    } else {
      // fallback polling
      patch(id, { stage: "processing", message: "Processing on server…", jobStatus: "processing", jobProgress: 5 });
      for (;;) {
        // eslint-disable-next-line no-await-in-loop
        const r = await fetch(`${API_BASE}/api/rag/status/${id}`).then(x => x.json()).catch(() => null);
        if (r?.ok) {
          const j = r.job;
          patch(id, {
            jobStatus: j.status, jobProgress: j.progress, message: j.message,
            stage: j.status === "done" ? "done" : (j.status === "error" ? "error" : "processing")
          });
          if (j.status === "done" || j.status === "error") break;
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise(res => setTimeout(res, 1200));
      }
    }
  }

  // tiny helper to bind a fresh SSE instance per file
  function useSSEJobInstance(jobId: string, onUpdate: (u: JobUpdate) => void) {
    const { start, stop, supported } = useSSEJob(jobId, (u) => {
      onUpdate(u);
      if (u.ok && u.job && (u.job.status === "done" || u.job.status === "error")) {
        stop();
      }
    });
    return { start, stop, supported };
  }

  async function startAll() {
    if (!API_BASE) {
      alert("Set API base env: VITE_API_BASE / NEXT_PUBLIC_API_BASE / REACT_APP_API_BASE");
      return;
    }
    for (const it of items) {
      if (it.stage === "queued" || it.stage === "error") {
        // eslint-disable-next-line no-await-in-loop
        await processOne(it);
      }
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 800 }}>
      <h3>Multi-file Upload + PUT Progress + Live Server Status (SSE)</h3>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: "2px dashed", borderColor: dragOver ? "#4f46e5" : "#999",
          padding: 22, borderRadius: 10, textAlign: "center",
          background: dragOver ? "rgba(79,70,229,0.06)" : "transparent",
          cursor: "pointer", marginBottom: 12
        }}
      >
        <div style={{ fontSize: 14, opacity: 0.8 }}>
          {dragOver ? "Drop files…" : "Click or drag multiple files here"}
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          onChange={(e) => addFiles(e.target.files)}
          style={{ display: "none" }}
        />
      </div>

      <button
        onClick={startAll}
        disabled={!canStart}
        style={{
          padding: "10px 14px", borderRadius: 8, border: "none",
          background: canStart ? "#4f46e5" : "#bbb", color: "white",
          cursor: canStart ? "pointer" : "not-allowed", marginBottom: 12
        }}
      >
        Start Uploads
      </button>

      {items.length === 0 ? (
        <div style={{ opacity: 0.7 }}>No files queued.</div>
      ) : (
        <div>
          {items.map((it) => (
            <div key={it.id} style={{ borderBottom: "1px solid #eee", padding: "10px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                <strong>{it.file.name}</strong>
                <span style={{ opacity: 0.7 }}>
                  {it.stage}
                  {typeof it.putProgress === "number" && it.stage === "uploading" ? ` (${it.putProgress}%)` : ""}
                </span>
              </div>

              {/* PUT progress */}
              <div style={{ height: 6, background: "#eee", borderRadius: 6, overflow: "hidden", marginTop: 6 }}>
                <div style={{
                  width: `${it.putProgress}%`,
                  height: "100%",
                  background: it.stage === "error" ? "#b91c1c" : "#4f46e5",
                  transition: "width .12s linear"
                }} />
              </div>

              {/* Server job progress */}
              {typeof it.jobProgress === "number" && (
                <div style={{ height: 6, background: "#eee", borderRadius: 6, overflow: "hidden", marginTop: 6 }}>
                  <div style={{
                    width: `${it.jobProgress}%`,
                    height: "100%",
                    background: it.jobStatus === "error" ? "#b91c1c" : "#0ea5e9",
                    transition: "width .12s linear"
                  }} />
                </div>
              )}

              <div style={{ fontSize: 12, marginTop: 6, opacity: 0.9 }}>
                {it.message}
                {it.downloadUrl && <> · <a href={it.downloadUrl} target="_blank" rel="noreferrer">open</a></>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

