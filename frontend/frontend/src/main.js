const BASE = import.meta.env.VITE_BACKEND_URL || "";
document.title = "Friday Frontend";
const out = document.querySelector("#out");
const btnPing = document.querySelector("#ping");
const btnAsk = document.querySelector("#ask");
const inputQ = document.querySelector("#q");

// Show which backend we're using
const info = document.createElement("div");
info.style.margin = "8px 0";
info.style.fontSize = "12px";
info.textContent = `Backend: ${BASE || "(dev proxy → http://localhost:8000)"}`;
document.body.querySelector("div").insertBefore(info, out);

function show(obj){ out.textContent = JSON.stringify(obj, null, 2); }

btnPing?.addEventListener("click", async () => {
  out.textContent = "…";
  try {
    const r = await fetch(`${BASE}/api/health`);
    show(await r.json());
  } catch (e) { show({ error: String(e) }); }
});

btnAsk?.addEventListener("click", async () => {
  const q = inputQ.value;
  out.textContent = "…";
  try {
    const r = await fetch(`${BASE}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q })
    });
    show(await r.json());
  } catch (e) { show({ error: String(e) }); }
});

