import { API, BACKEND } from "../env.mjs";

const out = document.getElementById("out");
const btn = document.getElementById("ping");

// show where we're pointing
const base = document.getElementById("base");
if (base) base.textContent = `Backend: ${BACKEND}  |  API: ${API}`;

async function ping() {
  out.textContent = "…";
  try {
    const r = await fetch(`${API}/health`, { method: "GET" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    out.textContent = JSON.stringify(await r.json());
  } catch (e) {
    out.textContent = `Error: ${e.message}`;
  }
}

btn?.addEventListener("click", ping);











