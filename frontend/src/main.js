// frontend/src/main.js
// Small vanilla JS demo that reads the backend base from Vite env
// and calls /api/health and /api/ask on the BACKEND (never the static site).

const out = document.querySelector("#out");
const statusEl = document.querySelector("#status");
const pingBtn = document.querySelector("#ping");
const askForm = document.querySelector("#ask-form");
const askInput = document.querySelector("#ask-input");
const baseEl = document.querySelector("#base");

// 1) Resolve backend base URL from Vite env
//    REQUIRED: VITE_BACKEND_URL must be set at build time (Render “Environment”)
const BACKEND = import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, "");
if (!BACKEND) {
  baseEl.textContent = "ERROR: VITE_BACKEND_URL is empty";
} else {
  baseEl.textContent = `Backend: ${BACKEND}`;
}

function setStatus(t) {
  statusEl.textContent = t;
}

async function getJSON(path) {
  const url = `${BACKEND}${path}`;
  const res = await fetch(url, { credentials: "omit" });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${url}\n${txt}`);
  }
  return res.json();
}

pingBtn?.addEventListener("click", async () => {
  setStatus("Pinging …");
  out.textContent = "";
  try {
    const data = await getJSON("/api/health");
    setStatus("OK");
    out.textContent = JSON.stringify(data);
  } catch (err) {
    setStatus("ERROR");
    out.textContent = String(err);
  }
});

askForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus("Asking …");
  out.textContent = "";
  const q = askInput.value.trim();
  try {
    const res = await fetch(`${BACKEND}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    setStatus("OK");
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    setStatus("ERROR");
    out.textContent = String(err);
  }
});






