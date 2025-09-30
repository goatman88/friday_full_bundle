// frontend/src/main.js

// Decide the backend base URL.
// - In PRODUCTION (Render), we expect VITE_BACKEND_URL to be defined in the
//   frontend service’s Environment tab (e.g. https://friday-backend-xxxx.onrender.com).
// - In DEV, we use the /api proxy defined in vite.config.js.
const BASE =
  (import.meta.env.PROD && import.meta.env.VITE_BACKEND_URL)
    ? import.meta.env.VITE_BACKEND_URL
    : "/api";

// --- tiny UI helpers ---
const out = document.querySelector("#out");
const baseEl = document.querySelector("#base");
const btnPing = document.querySelector("#ping");
const askForm = document.querySelector("#ask-form");
const askInput = document.querySelector("#ask-input");

function show(text) {
  out.textContent = (typeof text === "string") ? text : JSON.stringify(text);
}

function resToText(res) {
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

// Show what BASE we’re using (helps diagnose prod vs dev)
if (baseEl) baseEl.textContent = `BASE: ${BASE}`;

// Ping button -> GET /api/health
if (btnPing) {
  btnPing.addEventListener("click", async () => {
    show("…");
    try {
      const res = await fetch(`${BASE}/api/health`, { method: "GET" });
      const payload = await resToText(res);
      show(payload);
    } catch (e) {
      show(`Error: ${e.message}`);
    }
  });
}

// Ask form -> POST /api/ask { q }
if (askForm) {
  askForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const q = (askInput?.value || "").trim();
    if (!q) return;
    show("…");
    try {
      const res = await fetch(`${BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q })
      });
      const payload = await resToText(res);
      show(payload);
    } catch (e) {
      show(`Error: ${e.message}`);
    }
  });
}

// Also log the BASE to the console for quick checks
console.log("[Friday Frontend] Using BASE:", BASE, {
  PROD: import.meta.env.PROD,
  VITE_BACKEND_URL: import.meta.env.VITE_BACKEND_URL
});


