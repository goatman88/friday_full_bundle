import { api } from "./env.mjs";

const out = document.getElementById("out");
const ping = document.getElementById("ping");
const base = document.getElementById("base");

function show(msg) {
  out.textContent = msg;
}

function status(s) {
  const el = document.getElementById("status");
  if (el) el.textContent = s;
}

async function getJSON(url, opts = {}) {
  const r = await fetch(url, { ...opts, headers: { "content-type": "application/json", ...(opts.headers || {}) } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

(async () => {
  // show which backend the bundle is using
  base.textContent = `Backend: ${api("").replace(/\/$/, "")}`;
})();

ping?.addEventListener("click", async () => {
  try {
    status("OK");
    const data = await getJSON(api("/api/health"));
    show(JSON.stringify(data));
  } catch (e) {
    status("ERROR");
    show(String(e.message || e));
  }
});

// Mini demo inputs (optional)
document.getElementById("ask-form")?.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = document.getElementById("ask-input")?.value || "";
  try {
    const data = await getJSON(api("/api/ask"), { method: "POST", body: JSON.stringify({ q }) });
    show(JSON.stringify(data));
  } catch (e) {
    show(String(e.message || e));
  }
});











