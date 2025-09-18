// src/App.jsx
import React, { useEffect, useState } from "react";
import MultiUploader from "./multi-uploader.jsx";
import { API_BASE, getHealth, queryRag } from "./api";

export default function App() {
  const [alive, setAlive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("what did the fox do?");
  const [index, setIndex] = useState("both");
  const [topK, setTopK] = useState(5);
  const [answer, setAnswer] = useState("");
  const [hits, setHits] = useState([]);

  useEffect(() => {
    (async () => {
      try { await getHealth(); setAlive(true); }
      catch { setAlive(false); }
    })();
  }, []);

  async function runQuery(e) {
    e?.preventDefault?.();
    setBusy(true);
    setAnswer("");
    setHits([]);
    try {
      const res = await queryRag({ q, top_k: Number(topK), index });
      setAnswer(res.answer ?? "");
      const rawHits = res.hits ?? {};
      const parsed = Object.values(rawHits).map((h) => typeof h === "string" ? h : JSON.stringify(h));
      setHits(parsed);
    } catch (err) {
      setAnswer(`Error: ${err?.message || err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", color: "#e5e7eb", background: "#0b1020", minHeight: "100vh" }}>
      <header style={{ padding: "16px 20px", borderBottom: "1px solid #111827", background: "#0f162e", position: "sticky", top: 0 }}>
        <h2 style={{ margin: 0 }}>Friday • RAG Console</h2>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          API base: <code>{API_BASE}</code> • Health:{" "}
          <span style={{ color: alive ? "#10b981" : "#ef4444" }}>{alive ? "ok" : "down"}</span>
        </div>
      </header>

      <main style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16, padding: 16, maxWidth: 1000, margin: "0 auto" }}>
        <MultiUploader />

        <section style={{ border: "1px solid #111827", borderRadius: 12, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Ask your index</h3>
          <form onSubmit={runQuery} style={{ display: "grid", gap: 8 }}>
            <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3}
                      placeholder="Ask a question…" style={{ resize: "vertical", padding: 10, borderRadius: 8, border: "1px solid #1f2937", background: "#0b1220", color: "#e5e7eb" }} />
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <label>Index:
                <select value={index} onChange={(e) => setIndex(e.target.value)} style={{ marginLeft: 6 }}>
                  <option value="both">both</option>
                  <option value="faiss_local">faiss_local</option>
                  <option value="s3_ingest">s3_ingest</option>
                </select>
              </label>
              <label>top_k:
                <input type="number" min={1} max={20} value={topK} onChange={(e) => setTopK(e.target.value)} style={{ marginLeft: 6, width: 80 }} />
              </label>
              <button disabled={busy} type="submit">
                {busy ? "Querying…" : "Query"}
              </button>
            </div>
          </form>

          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #111827" }}>
            <div style={{ marginBottom: 8, fontWeight: 600 }}>Answer</div>
            <div style={{ whiteSpace: "pre-wrap", background: "#0b1220", border: "1px solid #1f2937", padding: 12, borderRadius: 8 }}>
              {answer || <span style={{ opacity: 0.6 }}>No answer yet.</span>}
            </div>
            {!!hits.length && (
              <>
                <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 600 }}>Hits</div>
                <ol style={{ marginTop: 0 }}>
                  {hits.map((h, i) => (
                    <li key={i} style={{ opacity: 0.9 }}>
                      <code style={{ fontSize: 12 }}>{h}</code>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

