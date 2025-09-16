import React, { useCallback, useRef, useState } from "react";
import API_BASE from "../lib/apiBase";

type FileState = {
  id: string;            // external_id
  file: File;
  progress: number;      // 0..100 (PUT to S3)
  phase: "queued" | "signing" | "uploading" | "confirming" | "done" | "error";
  message?: string;
  downloadUrl?: string;
};

function putWithProgress(url: string, file: File, contentType: string, onProgress: (pct: number) => void) {
  // Use XHR to get upload progress (fetch doesn't expose upload progress)
  return new Promise<Response>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Type", contentType || "application/octet-stream");
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable) {
        const pct = Math.round((evt.loaded / evt.total) * 100);
        onProgress(pct);
      }
    };
    xhr.onload = () => {
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (!ok) {
        reject(new Error(`S3 PUT failed: ${xhr.status} ${xhr.responseText || ""}`));
        return;
      }
      // fabricate a fetch-like Response
      resolve(new Response(xhr.responseText, { status: xhr.status }));
    };
    xhr.onerror = () => reject(new Error("Network error during S3 PUT"));
    xhr.send(file);
  });
}

export default function MultiUploader() {
  const [files, setFiles] = useState<FileState[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    const next: FileState[] = Array.from(picked).map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      progress: 0,
      phase: "queued",
    }));
    setFiles((prev) => [...prev, ...next]);
  }, []);

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const onPickClick = () => inputRef.current?.click();

  async function processOne(item: FileState) {
    const { file, id } = item;
    const contentType = file.type || "application/octet-stream";

    // 1) Presign
    update(item.id, { phase: "signing", message: "Requesting presigned URL…" });
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_type: contentType })
    }).then(r => r.json()).catch(e => ({ ok: false, error: String(e) }));

    if (!ask?.ok || !ask.url || !ask.s3_uri) {
      update(item.id, { phase: "error", message: "Presign failed: " + (ask?.error || "unknown") });
      return;
    }

    // 2) PUT to S3 with progress
    update(item.id, { phase: "uploading", message: "Uploading to S3…", progress: 0 });
    try {
      await putWithProgress(ask.url, file, contentType, (pct) => {
        update(item.id, { progress: pct });
      });
    } catch (err: any) {
      update(item.id, { phase: "error", message: err?.message || "Upload failed" });
      return;
    }

    // 3) Confirm (server will parse/index)
    update(item.id, { phase: "confirming", message: "Confirming & indexing…" });
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri: ask.s3_uri, title: file.name, external_id: id })
    }).then(r => r.json()).catch(e => ({ ok: false, error: String(e) }));

    if (!confirm?.ok) {
      update(item.id, { phase: "error", message: "Confirm failed: " + (confirm?.error || "unknown") });
      return;
    }

    // 4) Optional: presigned GET to show link
    const got = await fetch(
      `${API_BASE}/api/rag/file_url?external_id=${encodeURIComponent(id)}`
    ).then(r => r.json()).catch(() => ({} as any));

    update(item.id, {
      phase: "done",
      progress: 100,
      message: "Done",
      downloadUrl: got?.ok ? got.url : undefined
    });
  }

  function update(id: string, patch: Partial<FileState>) {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  }

  async function startAll() {
    if (!API_BASE) {
      alert("Set your API base env (VITE_API_BASE / NEXT_PUBLIC_API_BASE / REACT_APP_API_BASE).");
      return;
    }
    // run sequentially (simple), or in parallel with Promise.all for speed
    for (const item of files) {
      if (item.phase === "queued" || item.phase === "error") {
        // eslint-disable-next-line no-await-in-loop
        await processOne(item);
      }
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 700 }}>
      <h3 style={{ marginTop: 0 }}>Multi-file Upload (Drag & Drop + Progress + Indexing)</h3>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        style={{
          border: "2px dashed",
          borderColor: dragOver ? "#4f46e5" : "#999",
          padding: 24,
          borderRadius: 10,
          background: dragOver ? "rgba(79,70,229,0.06)" : "transparent",
          textAlign: "center",
          cursor: "pointer",
          marginBottom: 12
        }}
        onClick={onPickClick}
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
        disabled={files.length === 0}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "none",
          background: files.length ? "#4f46e5" : "#bbb",
          color: "white",
          cursor: files.length ? "pointer" : "not-allowed",
          marginBottom: 14
        }}
      >
        Start Uploads
      </button>

      {files.length === 0 ? (
        <div style={{ opacity: 0.7 }}>No files queued.</div>
      ) : (
        <div>
          {files.map((f) => (
            <div key={f.id} style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                <strong>{f.file.name}</strong>
                <span style={{ opacity: 0.7 }}>{f.phase} {f.progress ? `(${f.progress}%)` : ""}</span>
              </div>
              <div style={{
                height: 8, background: "#eee", borderRadius: 6, overflow: "hidden", marginTop: 6
              }}>
                <div style={{
                  width: `${f.progress}%`,
                  height: "100%",
                  background: f.phase === "error" ? "#b91c1c" : "#4f46e5",
                  transition: "width .15s linear"
                }} />
              </div>
              <div style={{ fontSize: 12, marginTop: 6, opacity: 0.85 }}>
                {f.message}
                {f.downloadUrl && (
                  <>
                    {" · "}
                    <a href={f.downloadUrl} target="_blank" rel="noreferrer">open</a>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
