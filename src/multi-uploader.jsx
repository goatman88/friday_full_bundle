// src/multi-uploader.jsx
import React, { useCallback, useMemo, useRef, useState } from "react";
import { API_BASE, confirmUpload, createUploadUrl, putBytes } from "./api";

// small helper
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const readFileAsArrayBuffer = (file) =>
  new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsArrayBuffer(file);
  });

export default function MultiUploader() {
  const [indexTarget, setIndexTarget] = useState("both"); // 'faiss_local' | 's3_ingest' | 'both'
  const [collection, setCollection] = useState("default");
  const [chunkSize, setChunkSize] = useState(800);
  const [overlap, setOverlap] = useState(120);
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState([]); // progress rows
  const inputRef = useRef(null);

  const onPick = useCallback(() => inputRef.current?.click(), []);
  const onDrop = useCallback(async (e) => {
    e.preventDefault();
    const files = [...e.dataTransfer.files];
    if (files.length) await ingestFiles(files);
  }, [indexTarget, collection, chunkSize, overlap]);

  const onChoose = useCallback(async (e) => {
    const files = [...e.target.files];
    if (files.length) await ingestFiles(files);
    e.target.value = ""; // reset
  }, [indexTarget, collection, chunkSize, overlap]);

  const borderColor = useMemo(() => ({
    both: "#7c3aed",
    faiss_local: "#059669",
    s3_ingest: "#2563eb",
  }[indexTarget] || "#6b7280"), [indexTarget]);

  async function ingestFiles(files) {
    setStatus(`Uploading ${files.length} item(s)…`);
    const next = [];

    for (const file of files) {
      const row = { name: file.name, size: file.size, step: "requesting upload_url…" };
      next.push(row);
      setRows(r => [...r, row]);

      try {
        const { token, put_url } = await createUploadUrl();
        row.step = "uploading…";
        setRows(r => [...r]);

        const buf = await readFileAsArrayBuffer(file);
        await putBytes(put_url, buf, file.type || "application/octet-stream");

        row.step = "confirming…";
        setRows(r => [...r]);

        const result = await confirmUpload({
          token,
          collection,
          chunk_size: Number(chunkSize),
          overlap: Number(overlap),
          index: indexTarget,
        });

        row.step = `indexed ✓  chunks=${result.chunks}  index=${result.index}`;
        row.ok = true;
        setRows(r => [...r]);
        await sleep(100);
      } catch (err) {
        row.step = `error: ${err?.message || err}`;
        row.ok = false;
        setRows(r => [...r]);
      }
    }
    setStatus("Done.");
  }

  return (
    <div style={{ border: `2px dashed ${borderColor}`, borderRadius: 12, padding: 16, background: "#0b1220", color: "#e5e7eb" }}
         onDragOver={(e) => e.preventDefault()}
         onDrop={onDrop}>
      <h3 style={{ margin: 0, marginBottom: 8 }}>Upload & index</h3>
      <p style={{ marginTop: 0 }}>
        Drag files here or <button onClick={onPick}>choose</button>. They’ll be chunked and added to <code>{indexTarget}</code>.
      </p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
        <label>Index:
          <select value={indexTarget} onChange={(e) => setIndexTarget(e.target.value)} style={{ marginLeft: 6 }}>
            <option value="both">both (recommended)</option>
            <option value="faiss_local">faiss_local</option>
            <option value="s3_ingest">s3_ingest</option>
          </select>
        </label>

        <label>Collection:
          <input value={collection} onChange={(e) => setCollection(e.target.value)} style={{ marginLeft: 6 }} />
        </label>

        <label>Chunk size:
          <input type="number" min={200} max={2000} step={50}
                 value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} style={{ width: 90, marginLeft: 6 }} />
        </label>

        <label>Overlap:
          <input type="number" min={0} max={400} step={10}
                 value={overlap} onChange={(e) => setOverlap(e.target.value)} style={{ width: 90, marginLeft: 6 }} />
        </label>
      </div>

      <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 12 }}>
        API base: <code>{API_BASE}</code> • {status}
      </div>

      <input ref={inputRef} type="file" multiple style={{ display: "none" }} onChange={onChoose} />

      <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #1f2937" }}>
            <th>Name</th><th>Size</th><th>Step</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #111827" }}>
              <td>{r.name}</td>
              <td>{r.size?.toLocaleString?.() ?? ""}</td>
              <td style={{ color: r.ok === true ? "#10b981" : r.ok === false ? "#ef4444" : "#e5e7eb" }}>{r.step}</td>
            </tr>
          ))}
          {!rows.length && (
            <tr><td colSpan={3} style={{ opacity: 0.6 }}>No uploads yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}



