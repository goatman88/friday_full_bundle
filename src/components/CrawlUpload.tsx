import React, { useState } from "react";
import API_BASE from "../lib/apiBase";

export default function CrawlUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [href, setHref] = useState("");

  async function run() {
    if (!file) return setMsg("Pick a file first.");
    const content_type = file.type || "application/octet-stream";

    setMsg("Presigning…");
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_type })
    }).then(r => r.json());

    if (!ask.ok) return setMsg("Presign failed: " + (ask.error || "unknown"));

    setMsg("Uploading…");
    const put = await fetch(ask.url, {
      method: "PUT",
      headers: { "Content-Type": content_type },
      body: file
    });
    if (!put.ok) return setMsg("S3 PUT failed: " + put.status);

    setMsg("Confirming…");
    const external_id = crypto.randomUUID();
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri: ask.s3_uri, title: file.name, external_id })
    }).then(r => r.json());

    if (!confirm.ok) return setMsg("Confirm failed: " + (confirm.error || "unknown"));

    const got = await fetch(
      `${API_BASE}/api/rag/file_url?external_id=${encodeURIComponent(external_id)}`
    ).then(r => r.json());

    setMsg("Done ✅");
    if (got.ok) setHref(got.url);
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Crawl Upload</h3>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button onClick={run} style={{ marginLeft: 8 }}>Upload</button>
      <div style={{ marginTop: 8 }}>{msg}</div>
      {href && <a href={href} target="_blank" rel="noreferrer">open</a>}
    </div>
  );
}

