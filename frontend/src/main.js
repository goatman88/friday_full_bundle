// Friday frontend main.js — uses a single env var:
//   VITE_BACKEND_URL  (e.g. https://friday-backend-ksep.onrender.com)

const API_BASE = (import.meta.env?.VITE_BACKEND_URL || "").replace(/\/+$/, "");
const $ = (sel) => document.querySelector(sel);

function setStatus(msg, ok = true) {
  const out = $("#out");
  out.textContent = msg;
  out.style.color = ok ? "#222" : "#b00020";
}

function showBase() {
  const base = $("#base");
  base.textContent = API_BASE ? `Backend: ${API_BASE}` : "Backend: <not set>";
  base.style.color = API_BASE ? "#222" : "#b00020";
}

// simple GET helper
async function getJson(path) {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// wire UI
function wire() {
  $("#ping")?.addEventListener("click", async () => {
    setStatus("…pinging…");
    try {
      const data = await getJson("/api/health");
      setStatus(JSON.stringify(data));
    } catch (e) {
      setStatus(`Error: ${e.message}`, false);
    }
  });

  const askForm = $("#ask-form");
  askForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#ask-input")?.value ?? "";
    setStatus("…asking…");
    try {
      const url = `${API_BASE}/api/ask`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStatus(JSON.stringify(data));
    } catch (e) {
      setStatus(`Error: ${e.message}`, false);
    }
  });
}

// boot
showBase();
wire();








