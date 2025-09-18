import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || ""; // e.g. "" for same-origin, or "https://friday-099e.onrender.com"

export default function App() {
  const [health, setHealth] = useState("checking…");

  useEffect(() => {
    const url = `${API_BASE}/api/health`;
    fetch(url)
      .then(r => r.json())
      .then(j => setHealth(JSON.stringify(j)))
      .catch(e => setHealth(`error: ${e.message}`));
  }, []);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif" }}>
      <h1>Friday Frontend</h1>
      <p><b>Health:</b> {health}</p>

      <hr />

      <p>
        Try POSTing a RAG query from the console:
      </p>
      <pre style={{ background: "#f6f8fa", padding: 12, borderRadius: 6 }}>
{`fetch("${API_BASE}/api/rag/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ q: "what did the fox do?", top_k: 5, index: "both" })
}).then(r => r.json()).then(console.log);`}
      </pre>
    </div>
  );
}


