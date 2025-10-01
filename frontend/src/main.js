// frontend/src/main.js

// Decide backend base URL:
// - In Render (prod), we bake VITE_BACKEND_URL at build time.
// - In local dev (vite), we rely on the dev proxy to /api.
const BASE =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_BACKEND_URL) ||
  "/api";

const out = document.querySelector("#out");
const baseEl = document.querySelector("#base");
const pingBtn = document.querySelector("#ping");
const form = document.querySelector("#ask-form");
const askInput = document.querySelector("#ask-input");

// Show where we're pointing
baseEl.textContent = `BASE = ${BASE}`;

function show(obj) {
  out.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Wire up the ping button -> GET /api/health
pingBtn.addEventListener("click", async () => {
  show("…");
  try {
    const data = await fetchJSON(`${BASE}/health`);
    show(data);
  } catch (err) {
    show(`ERROR: ${err.message}`);
  }
});

// Simple POST /api/ask demo
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  show("…");
  try {
    const q = askInput.value.trim();
    const data = await fetchJSON(`${BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
    });
    show(data);
  } catch (err) {
    show(`ERROR: ${err.message}`);
  }
});




