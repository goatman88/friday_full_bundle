import React, { useCallback, useMemo, useState } from "react";

const API_BASE =
  import.meta?.env?.VITE_API_BASE ||
  (process as any)?.env?.NEXT_PUBLIC_API_BASE ||
  (process as any)?.env?.REACT_APP_API_BASE ||
  "";

type UploadState = "idle" | "asking" | "putting" | "confirming" | "done" | "error";

export default function DirectUpload() {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadState>("idle");
  const [message, setMessage] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");

  const onFilePick = (f: File | null) => {
    setFile(f);
    setMessage(f ? `Selected: ${f.name}` : "");
    setDownloadUrl("");
    setStatus("idle");
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilePick(e.target.files?.[0] || null);
  };

  const onDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0] || null;
    onFilePick(f);
  }, []);

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const canUpload = useMemo(() => !!file && !!API_BASE, [file]);

  async function handleUpload() {
    if (!file) return;
    setStatus("asking");
    setMessage("Requesting presigned PUT…");

    // 1) Ask backend for a presigned PUT URL (must pass the same Content-Type you will PUT with)
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || "application/octet-stream"
      })
    }).then(r => r.json());

    if (!ask.ok) {
      setStatus("error");
      setMessage("Failed to get upload URL: " + (ask.error || "unknown"));
      return;
    }

    const { url, s3_uri } = ask;

    // 2) PUT to S3 (Content-Type must match the presign)
    setStatus("putting");
    setMessage("Uploading to S3…");
    const put = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file
    });

    if (!put.ok) {
      const text = await put.text().catch(() => "");
      setStatus("error");
      setMessage(`S3 PUT failed: ${put.status} ${text}`.trim());
      return;
    }

    // 3) Confirm + index pointer (optionally pass content if you extracted on client)
    setStatus("confirming");
    setMessage("Confirming upload…");
    const external_id = crypto.randomUUID();
    const title = file.name;

    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri, title, external_id })
    }).then(r => r.json());

    if (!confirm.ok) {
      setStatus("error");
      setMessage("Confirm failed: " + (confirm.error || "unknown"));
      return;
    }

    // 4) Get a presigned GET to show user
    const got = await fetch(
      `${API_BASE}/api/rag/file_url?external_id=${encodeURIComponent(external_id)}`
    ).then(r => r.json());

    if (got.ok && got.url) {
      setDownloadUrl(got.url);
      setStatus("done");
      setMessage("Done ✅");
    } else {
      setStatus("done");
      setMessage("Indexed, but couldn’t fetch download URL.");
    }
  }

  return (
    <div style={{ maxWidth: 520, padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h3 style={{ margin: 0 }}>Direct upload to S3</h3>
      <p style={{ margin: "6px 0 12px", opacity: 0.75 }}>
        Drag a file here or pick one. Then it’ll presign → PUT → confirm → link.
      </p>

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        style={{
          border: "2px dashed",
          borderColor: dragOver ? "#4f46e5" : "#999",
          padding: 24,
          borderRadius: 10,
          textAlign: "center",
          background: dragOver ? "rgba(79,70,229,0.06)" : "transparent",
          transition: "all .12s ease"
        }}
      >
        <input
          type="file"
          onChange={onInputChange}
          style={{ display: "block", margin: "0 auto 8px" }}
        />
        <div style={{ fontSize: 13, opacity: 0.7 }}>
          {dragOver ? "Drop it!" : "…or drag & drop a file here"}
        </div>
      </div>

      <button
        onClick={handleUpload}
        disabled={!canUpload || status === "asking" || status === "putting" || status === "confirming"}
        style={{
          marginTop: 12,
          padding: "10px 14px",
          borderRadius: 8,
          border: "none",
          background: canUpload ? "#4f46e5" : "#bbb",
          color: "white",
          cursor: canUpload ? "pointer" : "not-allowed"
        }}
      >
        {status === "asking" ? "Requesting…" :
         status === "putting" ? "Uploading…" :
         status === "confirming" ? "Confirming…" :
         "Upload"}
      </button>

      <div style={{ marginTop: 12, fontSize: 14 }}>{message}</div>

      {downloadUrl && (
        <div style={{ marginTop: 10 }}>
          <a href={downloadUrl} target="_blank" rel="noreferrer">
            Open file (presigned GET)
          </a>
        </div>
      )}

      {!API_BASE && (
        <div style={{ marginTop: 10, color: "#b91c1c", fontSize: 13 }}>
          Set your API base in env:
          <pre style={{ margin: "6px 0 0" }}>
{`REACT_APP_API_BASE=... (CRA)
VITE_API_BASE=... (Vite)
NEXT_PUBLIC_API_BASE=... (Next.js)`}
          </pre>
        </div>
      )}
    </div>
  );
}
