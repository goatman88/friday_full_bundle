import React, { useCallback, useMemo, useState } from "react";
import API_BASE from "../lib/apiBase";

type Phase = "idle" | "asking" | "putting" | "confirming" | "done" | "error";

export default function DragDropUpload() {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [msg, setMsg] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");

  const onFiles = (f: File | null) => {
    setFile(f);
    setDownloadUrl("");
    setMsg(f ? `Selected: ${f.name}` : "");
    setPhase("idle");
  };

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragOver(false);
    onFiles(e.dataTransfer.files?.[0] || null);
  }, []);

  const canUpload = useMemo(() => !!file && !!API_BASE, [file]);

  async function handleUpload() {
    if (!file) return;
    setPhase("asking"); setMsg("Requesting presigned PUT…");

    // 1) Presign
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || "application/octet-stream"
      })
    }).then(r => r.json());

    if (!ask.ok) {
      setPhase("error"); setMsg("Failed to get upload URL: " + (ask.error || "unknown"));
      return;
    }
    const { url, s3_uri } = ask;

    // 2) PUT to S3
    setPhase("putting"); setMsg("Uploading to S3…");
    const put = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file
    });
    if (!put.ok) {
      setPhase("error");
      setMsg(`S3 PUT failed: ${put.status} ${await put.text().catch(()=> "")}`);
      return;
    }

    // 3) Confirm + index
    setPhase("confirming"); setMsg("Confirming upload…");
    const external_id = crypto.randomUUID();
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri, title: file.name, external_id })
    }).then(r => r.json());

    if (!confirm.ok) {
      setPhase("error"); setMsg("Confirm failed: " + (confirm.error || "unknown"));
      return;
    }

    // 4) Presigned GET
    const got = await fetch(
      `${API_BASE}/api/rag/file_url?external_id=${encodeURIComponent(external_id)}`
    ).then(r => r.json());

    if (got.ok && got.url) {
      setDownloadUrl(got.url);
      setPhase("done"); setMsg("Done ✅");
    } else {
      setPhase("done"); setMsg("Indexed, but couldn’t fetch download URL.");
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 520 }}>
      <h3>Drag & Drop Upload</h3>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          border: "2px dashed",
          borderColor: dragOver ? "#4f46e5" : "#999",
          padding: 24,
          borderRadius: 10,
          textAlign: "center",
          background: dragOver ? "rgba(79,70,229,0.06)" : "transparent",
          transition: "all .12s"
        }}
      >
        <input
          type="file"
          onChange={(e) => onFiles(e.target.files?.[0] || null)}
          style={{ display: "block", margin: "0 auto 8px" }}
        />
        <div style={{ fontSize: 13, opacity: 0.75 }}>
          {dragOver ? "Drop it!" : "Pick or drag a file here"}
        </div>
      </div>

      <button
        onClick={handleUpload}
        disabled={!canUpload || phase === "asking" || phase === "putting" || phase === "confirming"}
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
        {phase === "asking" ? "Requesting…" :
         phase === "putting" ? "Uploading…" :
         phase === "confirming" ? "Confirming…" :
         "Upload"}
      </button>

      <div style={{ marginTop: 10 }}>{msg}</div>
      {downloadUrl && (
        <div style={{ marginTop: 8 }}>
          <a href={downloadUrl} target="_blank" rel="noreferrer">Open file (presigned GET)</a>
        </div>
      )}

      {!API_BASE && (
        <div style={{ marginTop: 8, color: "#b91c1c", fontSize: 13 }}>
          Set your API base env first.
        </div>
      )}
    </div>
  );
}
