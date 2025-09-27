const form = document.getElementById("askForm");
const out  = document.getElementById("out");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("q").value || "";
  try {
    const r = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q })
    });
    out.textContent = await r.text();
  } catch (err) {
    out.textContent = String(err);
  }
});










