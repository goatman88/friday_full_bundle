const \$ = (s) => document.querySelector(s);
document.querySelector("#ping").addEventListener("click", async () => {
  try {
    const res = await fetch("http://localhost:8000/api/health");
    document.querySelector("#out").textContent =
      JSON.stringify(await res.json(), null, 2);
  } catch (err) {
    document.querySelector("#out").textContent = String(err);
  }
});
