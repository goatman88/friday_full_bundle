import { useEffect, useState } from "react";
import { healthCheck } from "./api";

export default function App() {
  const [status, setStatus] = useState("…");
  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

  useEffect(() => {
    healthCheck()
      .then((j) => setStatus(j.status))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div style={{ maxWidth: 720, margin: "3rem auto", fontFamily: "Inter, system-ui, sans-serif" }}>
      <h1>🚀 Friday Frontend</h1>
      <p>
        API: <code>{apiBase}</code> — Health: <strong>{status}</strong>
      </p>
      {/* your UI here */}
    </div>
  );
}
