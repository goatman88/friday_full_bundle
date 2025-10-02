const BASE = import.meta.env.VITE_BACKEND_URL;

document.getElementById("base").textContent = BASE;

const out = document.getElementById("out");

// Ping backend
document.getElementById("ping").addEventListener("click", async () => {
  try {
    const res = await fetch(`${BASE}/api/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});

// Ask form
document.getElementById("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("ask-input").value;

  try {
    const res = await fetch(`${BASE}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
});





