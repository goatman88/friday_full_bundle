// src/multi-uploader.jsx
import React, { useCallback, useMemo, useRef, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/+$/, ""); // no trailing slash

function prettyBytes(n) {
  if (n === 0) return "0 B";
  const k = 1024;
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(n) / Math.log(k));
  return `${(n / Math.pow(k, i)).toFixed(1)} ${units[i]}`;
}

export default function MultiUploader() {
  const [queue, setQueue] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const accept = useMemo(
    () => ".pdf,.txt,.md,.docx,.pptx,.xlsx,.csv,.json,.html,.htm,.png,.jpg,.jpeg",
    []
  );

  const addFiles = useCallback((fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setQueue((prev) => [
      ...prev,
      ...files.map((f) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file: f,
        status: "queued", // queued | signing | uploading | confirming | done | error
        progress: 0,
        message: "",
        s3Url: null,
      })),
    ]);
  }, []);

  const onSelect = (e) => addFiles(e.target.files);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);

  async function presign(file) {
    const res = await fetch(`${API_BASE}/api/rag/presign_upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || "application/octet-stream",
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`presign failed (${res.status}): ${text}`);
    }
    return res.json(); // { put_url, s3_uri }
  }

  function putToS3(putUrl, file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", putUrl, true);
      xhr.setRequestHeader(
        "Content-Type",
        file.type || "application/octet-stream"
      );
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && onProgress) {
          onProgress(Math.round((evt.loaded / evt.total) * 100));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`S3 PUT failed: ${xhr.status} ${xhr.responseText}`));
      };
      xhr.onerror = () => reject(new Error("S3 PUT network error"));
      xhr.send(file);
    });
  }

  async function confirmUpload({ s3_uri, title, external_id, content }) {
    const res = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        s3_uri,
        title,
        external_id,
        content, // optional (for .txt etc) — backend can ignore if not needed
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`confirm failed (${res.status}): ${text}`);
    }
    return res.json();
  }

  const startAll = async () => {
    // kick off sequentially to keep logs clear (you can parallelize if you like)
    for (const item of queue) {
      if (item.status !== "queued" && item.status !== "error") continue;

      // mark signing
      setQueue((prev) =>
        prev.map((x) =>
          x.id === item.id ? { ...x, status: "signing", message: "" } : x
        )
      );

      try {
        const { put_url, s3_uri } = await presign(item.file);

        setQueue((prev) =>
          prev.map((x) =>
            x.id === item.id
              ? { ...x, status: "uploading", progress: 1, s3Url: s3_uri }
              : x
          )
        );

        await putToS3(put_url, item.file, (p) => {
          setQueue((prev) =>
            prev.map((x) =>
              x.id === item.id ? { ...x, progress: p } : x
            )
          );
        });

        setQueue((prev) =>
          prev.map((x) =>
            x.id === item.id ? { ...x, status: "confirming", progress: 100 } : x
          )
        );

        const title = item.file.name;
        const external_id = item.id;

        await confirmUpload({
          s3_uri,
          title,
          external_id,
          content: undefined,
        });

        setQueue((prev) =>
          prev.map((x) =>
            x.id === item.id ? { ...x, status: "done", message: "Indexed" } : x
          )
        );
      } catch (err) {
        setQueue((prev) =>
          prev.map((x) =>
            x.id === item.id
              ? {
                  ...x,
                  status: "error",
                  message: err?.message || String(err),
                }
              : x
          )
        );
      }
    }
  };

  const clearDone = () =>
    setQueue((prev) => prev.filter((x) => x.status !== "done"));

  return (
    <div style={{ maxWidth: 880, margin: "40px auto", padding: "0 16px" }}>
      <h2>Multi-file Uploader</h2>
      <p>
        Backend: <code>{API_BASE || "(missing VITE_API_BASE)"}</code>
      </p>

      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <button onClick={() => inputRef.current?.click()}>Choose files</button>
        <button onClick={startAll} disabled={!queue.some(q => q.status === "queued" || q.status === "error")}>
          Start upload
        </button>
        <button onClick={clearDone} disabled={!queue.some(q => q.status === "done")}>
          Clear completed
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple
        style={{ display: "none" }}
        onChange={onSelect}
      />

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        style={{
          border: "2px dashed #888",
          borderRadius: 10,
          padding: 24,
          textAlign: "center",
          background: dragOver ? "#f5f7ff" : "transparent",
          marginBottom: 20,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          Drag & drop files here
        </div>
        <div style={{ color: "#666", fontSize: 14 }}>
          Or click “Choose files”. Allowed: {accept}
        </div>
      </div>

      {!queue.length ? (
        <div style={{ color: "#666" }}>No files selected yet.</div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
          {queue.map((item) => (
            <li
              key={item.id}
              style={{
                border: "1px solid #ddd",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.file.name}
                  </div>
                  <div style={{ color: "#666", fontSize: 12 }}>
                    {item.file.type || "application/octet-stream"} • {prettyBytes(item.file.size)}
                  </div>
                </div>
                <div style={{ textTransform: "capitalize" }}>
                  {item.status}
                </div>
              </div>

              <div style={{ marginTop: 8, height: 8, background: "#eee", borderRadius: 999 }}>
                <div
                  style={{
                    width: `${item.progress || 0}%`,
                    height: "100%",
                    background: item.status === "error" ? "#e53935" : "#4caf50",
                    borderRadius: 999,
                    transition: "width 120ms linear",
                  }}
                />
              </div>

              {item.message && (
                <div style={{ marginTop: 8, color: item.status === "error" ? "#e53935" : "#2e7d32", fontSize: 13 }}>
                  {item.message}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
