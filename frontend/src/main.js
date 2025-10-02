// --- Friday Frontend main.js (works in dev + prod) ---

// If VITE_BACKEND_URL is provided, use it. Otherwise use "" (so /api goes through Vite proxy in dev)
const RAW = (import.meta.env?.VITE_BACKEND_URL || "").trim();
const BASE = RAW.endsWith("/") ? RAW.slice(0, -1) : RAW; // strip trailing slash if any

// tiny helper
const j = (sel) => document.querySelector(sel);
const out = j("#out");
const base = j("#base");
const btn = j("#ping");
const askForm = j("#ask-form");
const askInput = j("#ask-input");

// show what we're targeting so it's obvious
base.textContent = `Backend: ${BASE || "(dev proxy -> http://localhost:8000)"}`;

function show(result) {
  try { out.textContent = JSON.stringify(result, null, 2); }
  catch { out.textContent = String(result); }
}

async function hit(path, init) {
  const url = BASE ? `${BASE}${path}` : path;  // absolute in prod, relative in dev (proxy)
  const res = await fetch(url, {
    // CORS-safe defaults
    method: (init && init.method) || "GET",
    headers: { "Content-Type": "application/json", ...(init && init.headers) },
    body: init && init.body,
    mode: "cors",
    credentials: "omit",
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}${txt ? ` — ${txt}` : ""}`);
  }
  return res.json();
}

btn.addEventListener("click", async () => {
  out.textContent = "…";
  try {
    const data = await hit("/api/health");
    show(data);
  } catch (err) {
    show(`Error: ${err.message || err}`);
  }
});

askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  out.textContent = "…";
  try {
    const data = await hit("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question: askInput.value || "" }),
    });
    show(data);
  } catch (err) {
    show(`Error: ${err.message || err}`);
  }
});







