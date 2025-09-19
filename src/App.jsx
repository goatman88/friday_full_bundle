import React, { useEffect, useState } from "react";
import MultiUploader from "./multi-uploader";
import { API_BASE, health, queryRag } from "./api";

function QueryBox() {
  const [q, setQ] = useState("what did the fox do?");
  const [index, setIndex] = useState("both");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState("");
  const [hits, setHits] = useState({});

  async function onAsk(e) {
    e.preventDefault();
    setBusy(true);
    setAnswer("");
    setHits({});
    try {
      const data = await queryRag({ q, top_k: 5, index });
      setAnswer(data.answer ?? "");
      setHits(data.hits ?? {});
    } catch (err) {
      setAnswer(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <h2>🔎 Query</h2>
      <form onSubmit={onAsk} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          style={{ flex: "1 1 420px", minWidth: 260 }}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask your indexed data…"
        />
        <select value={index} onChange={(e) => setIndex(e.target.value)}>
          <option value="both">both</option>
          <option value="faiss">faiss (local)</option>
          <option value="s3">s3 (remote)</option>
        </select>
        <button type="submit" disabled={busy || !q.trim()}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>

      {answer && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 600 }}>Answer</div>
          <div style={{ padding: "8px 10px", background: "#f6f7fb", borderRadius: 8 }}>{answer}</div>
        </div>
      )}

      {hits && Object.keys(hits).length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: "pointer" }}>Show hits</summary>
          <pre
            style={{
              background: "#0b1020",
              color: "#d7e6ff",
              padding: 12,
              borderRadius: 8,
              overflowX: "auto",
              marginTop: 8,
            }}
          >
{JSON.stringify(hits, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}

export default function App() {
  const [healthState, setHealthState] = useState("checking…");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const h = await health();
        mounted && setHealthState(h?.status || JSON.stringify(h));
      } catch (e) {
        mounted && setHealthState(`error: ${e.message}`);
      }
    })();
    return () => (mounted = false);
  }, []);

  return (
    <main style={{ maxWidth: 960, margin: "32px auto", padding: "0 16px", lineHeight: 1.45 }}>
      <h1 style={{ marginBottom: 0 }}>🚀 Friday Frontend is Live</h1>
      <p style={{ color: "#666", marginTop: 8 }}>
        API: <code>{API_BASE}</code> • Health: <strong>{healthState}</strong>
      </p>

      <MultiUploader />
      <QueryBox />
    </main>
  );
}




