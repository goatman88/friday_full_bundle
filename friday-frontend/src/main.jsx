import React from "react";
import { createRoot } from "react-dom/client";
import { getHealth } from "./api";

function App() {
  const [status, setStatus] = React.useState("…");
  const api = import.meta.env.VITE_API_BASE;

  React.useEffect(() => {
    getHealth()
      .then(() => setStatus("ok"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div style={{ padding: 24, font: "16px/1.4 system-ui, sans-serif" }}>
      <h1>🚀 Friday Frontend</h1>
      <div>API: <code>{api}</code> — Health: <b>{status}</b></div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);



