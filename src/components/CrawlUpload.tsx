import React, { useState } from "react";
import API_BASE from "../lib/apiBase";

export default function CrawlUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");

  async function handleUpload() {
    if (!file) {
      setStatus("Pick a file first.");
      return;
    }
    setStatus("Requesting presigned PUT…");

    // 1) Ask backend for PUT URL (Content-Type must match your PUT)
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || "application/octet-stream"
      })
    }).then(r => r.json());

    if (!ask.ok) {
      setStatus("Failed to get upload URL: " + (ask.error || "unknown"));
      return;
    }
    const { url, s3_uri } = ask;

    // 2) PUT directly to S3
    setStatus("Uploading to S3…");
    const put = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file
    });
    if (!put.ok) {
      setStatus(`S3 PUT failed: ${put.status} ${await put.text().catch(()=> "")}`);
      return;
    }

    // 3) Confirm + index pointer
    setStatus("Confirming upload…");
    const external_id = crypto.randomUUID();
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri, title: file.name, external_id })
    }).then(r => r.json());

    if (!confirm.ok) {
      setStatus("Confirm failed: " + (confirm.error || "unknown"));
      return;
    }

    // 4) Get a presigned GET for the user
    const got = await fetch(
      `${API_BASE}/api/rag/file_url?external_id=${encodeURIComponent(external_id)}`
    ).then(r => r.json());

    if (got.ok && got.url) {
      setDownloadUrl(got.url);
      setStatus("Done ✅");
    } else {
      setStatus("Indexed, but couldn’t create download URL.");
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Crawl Upload</h3>
      <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
      <button onClick={handleUpload} style={{ marginLeft: 8 }}>Upload</button>
      <div style={{ marginTop: 8 }}>{status}</div>
      {downloadUrl && (
        <div style={{ marginTop: 8 }}>
          <a href={downloadUrl} target="_blank" rel="noreferrer">Open file (presigned GET)</a>
        </div>
      )}
      {!API_BASE && <div style={{ color: "#b91c1c" }}>Set API base env first.</div>}
    </div>
  );
}
