// Always use absolute backend URL provided by Vite env
const BACKEND = import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "");
const $ = (id) => document.getElementById(id);
const show = (id, v) => ($(id).textContent = typeof v === "string" ? v : JSON.stringify(v));

$("base").textContent = `BACKEND = ${BACKEND || "(missing)"}`;

async function getJSON(url, opts = {}) {
  const r = await fetch(url, { ...opts, headers: { "content-type": "application/json", ...(opts.headers || {}) } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

async function ping() {
  $("stat").textContent = "…";
  try {
    const json = await getJSON(`${BACKEND}/api/health`);
    $("out").textContent = JSON.stringify(json);
    $("stat").textContent = "OK";
  } catch (e) {
    $("out").textContent = `Error: ${e.message}`;
    $("stat").textContent = "ERROR";
  }
}

async function loadHealth() {
  try {
    const json = await getJSON(`${BACKEND}/api/health`);
    $("health").textContent = JSON.stringify(json);
  } catch (e) {
    $("health").textContent = `Error: ${e.message}`;
  }
}

$("ping").addEventListener("click", ping);

$("ask-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("ask-input").value.trim();
  if (!q) return;
  try {
    const json = await getJSON(`${BACKEND}/api/ask`, {
      method: "POST",
      body: JSON.stringify({ question: q })
    });
    $("out").textContent = JSON.stringify(json);
  } catch (e) {
    $("out").textContent = `Error: ${e.message}`;
  }
});

loadHealth();












