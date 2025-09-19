import React, { useMemo, useRef, useState } from "react";
import {
  API_BASE,
  requestUploadUrl,
  putToUrl,
  confirmUpload,
} from "./api";

const box = {
  border: "1px dashed #bbb",
  padding: "16px",
  borderRadius: 8,
  marginTop: 16,
};

export default function MultiUploader() {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);

  // Controls
  const [collection, setCollection] = useState("default");
  const [index, setIndex] = useState("both"); // "faiss" | "s3" | "both"
  const [chunkSize, setChunkSize] = useState(800);
  const [overlap, setOverlap] = useState(120);
  const [text, setText] = useState("");

  const canUpload = useMemo(
    () => text.trim().length > 0 || (fileRef.current && fileRef.current.files?.length),
    [text]
  );

  async function uploadBytes(bytes, contentType) {
    setStatus("Requesting upload URL…");
    const u = await requestUploadUrl(); // { token, put_url }
    setStatus("Uploading bytes…");
    await putToUrl(u.put_url, bytes, contentType);
    setStatus("Confirming (chunk + index)…");
    const summary = await confirmUpload({
      token: u.token,
      collection,
      chunk_size: Number(chunkSize),
      overlap: Number(overlap),
      index,
    });
    setResult(summary);
    setStatus("Done.");
  }

  async function onUploadText(e) {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      setBusy(true);
      const bytes = new TextEncoder().encode(text);
      await uploadBytes(bytes, "text/plain");
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onUploadFile(e) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    try {
      setBusy(true);
      const bytes = await file.arrayBuffer();
      await uploadBytes(bytes, file.type || "application/octet-stream");
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <h2>📤 Upload to Friday</h2>
      <p style={{ color: "#666", marginTop: -8 }}>
        API base: <code>{API_BASE}</code>
      </p>

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
        <label>
          <div style={{ fontSize: 12, color: "#555" }}>Collection</div>
          <input
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
            placeholder="default"
          />
        </label>
        <label>
          <div style={{ fontSize: 12, color: "#555" }}>Index</div>
          <select value={index} onChange={(e) => setIndex(e.target.value)}>
            <option value="both">both</option>
            <option value="faiss">faiss (local)</option>
            <option value="s3">s3 (remote)</option>
          </select>
        </label>
        <label>
          <div style={{ fontSize: 12, color: "#555" }}>Chunk size</div>
          <input
            type="number"
            min={100}
            max={4000}
            value={chunkSize}
            onChange={(e) => setChunkSize(e.target.value)}
          />
        </label>
        <label>
          <div style={{ fontSize: 12, color: "#555" }}>Overlap</div>
          <input
            type="number"
            min={0}
            max={1000}
            value={overlap}
            onChange={(e) => setOverlap(e.target.value)}
          />
        </label>
      </div>

      <div style={box}>
        <h3 style={{ marginTop: 0 }}>Paste text</h3>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          placeholder="Paste any text to index…"
          style={{ width: "100%", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" }}
        />
        <button onClick={onUploadText} disabled={busy || !text.trim()} style={{ marginTop: 8 }}>
          {busy ? "Uploading…" : "Upload text"}
        </button>
      </div>

      <div style={box}>
        <h3 style={{ marginTop: 0 }}>Upload a file</h3>
        <input ref={fileRef} type="file" />
        <button onClick={onUploadFile} disabled={busy || !fileRef.current?.files?.length} style={{ marginLeft: 8 }}>
          {busy ? "Uploading…" : "Upload file"}
        </button>
      </div>

      <div style={{ marginTop: 12, minHeight: 24 }}>
        {status && <div><strong>Status:</strong> {status}</div>}
      </div>

      {result && (
        <pre
          style={{
            background: "#0b1020",
            color: "#d7e6ff",
            padding: 12,
            borderRadius: 8,
            overflowX: "auto",
            marginTop: 12,
          }}
        >
{JSON.stringify(result, null, 2)}
        </pre>
      )}
    </section>
  );
}

