import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { API_BASE, getHealth } from "./api";

function App() {
  const [status, setStatus] = useState("…");
  useEffect(() => { getHealth().then(() => setStatus("ok"), () => setStatus("error")); }, []);
  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "system-ui, sans-serif" }}>
      <h1>🚀 Friday Frontend</h1>
      <p id="api">API: {API_BASE} — Health: {status}</p>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
