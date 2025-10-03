// frontend/src/main.js
const BACKEND = import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") || "";

const out = document.querySelector("#out");
const btn = document.querySelector("#ping");

// Small helper to show a line of text
function show(text) {
  out.textContent = typeof text === "string" ? text : JSON.stringify(text);
}

// Calls /api/health on the backend using the absolute host
async function ping() {
  const url = `${BACKEND}/api/health`;
  try {
    const res = await fetch(url, { method: "GET" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    show(data);
  } catch (err) {
    show(`Error: ${err.message || err}`);
  }
}

btn?.addEventListener("click", ping);

// Optional: kick one call on load so you can see status without clicking
// ping();












