// Always read the absolute backend base from an env var baked by Vite:
const BACKEND = import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, "");
const out = document.getElementById("out");
const askOut = document.getElementById("ask-out");
const status = document.getElementById("status");
const base = document.getElementById("base");
const ep = document.getElementById("endpoint");

function show(msg, ok = true) {
  status.textContent = (ok ? "Status: OK " : "Status: ERROR ") + msg;
}

function requireBackend() {
  if (!BACKEND) {
    show("VITE_BACKEND_URL is missing. Rebuild with that env var set.", false);
    throw new Error("Missing VITE_BACKEND_URL");
  }
}

function fmt(obj) { return JSON.stringify(obj, null, 2); }

async function ping() {
  requireBackend();
  const url = `${BACKEND}/api/health`;
  ep.textContent = url;
  try {
    const r = await fetch(url, { method: "GET" });
    if (!r.ok) {
      const text = await r.text();
      show(`HTTP ${r.status}`, false);
      out.textContent = text || `<empty body>`;
      return;
    }
    const data = await r.json();
    show("Fetched /api/health");
    out.textContent = fmt(data);
  } catch (err) {
    show("Failed to fetch", false);
    out.textContent = String(err);
  }
}

async function ask(q) {
  requireBackend();
  const url = `${BACKEND}/api/ask`;
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q })
    });
    const text = await r.text();
    if (!r.ok) {
      show(`POST /api/ask -> ${r.status}`, false);
      askOut.textContent = text || "<empty>";
      return;
    }
    // try to parse json, otherwise show raw text
    try { askOut.textContent = fmt(JSON.parse(text)); }
    catch { askOut.textContent = text; }
    show("Asked /api/ask");
  } catch (e) {
    show("Failed to POST", false);
    askOut.textContent = String(e);
  }
}

// Wire UI
document.getElementById("ping").addEventListener("click", ping);
document.getElementById("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  ask(document.getElementById("ask-input").value || "");
});

// Show which backend we will hit
base.textContent = `Backend: ${BACKEND || "(missing)"}`;













