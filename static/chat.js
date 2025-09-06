(function () {
  const $ = (sel) => document.querySelector(sel);

  const tokenInput = $("#token");
  const saveBtn    = $("#saveToken");
  const sendBtn    = $("#send");
  const clearBtn   = $("#clear");
  const copyBtn    = $("#copy");
  const msgInput   = $("#msg");
  const replyBox   = $("#reply");

  // Load saved token (dev convenience)
  const saved = localStorage.getItem("friday_api_token");
  if (saved) tokenInput.value = saved;

  saveBtn.addEventListener("click", () => {
    localStorage.setItem("friday_api_token", tokenInput.value.trim());
    saveBtn.textContent = "Saved ✓";
    setTimeout(() => (saveBtn.textContent = "Save"), 1200);
  });

  clearBtn.addEventListener("click", () => {
    msgInput.value = "";
    replyBox.textContent = "(cleared)";
  });

  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(replyBox.textContent || "");
      copyBtn.textContent = "Copied ✓";
      setTimeout(() => (copyBtn.textContent = "Copy"), 1200);
    } catch {}
  });

  sendBtn.addEventListener("click", async () => {
    const token = tokenInput.value.trim();
    const message = msgInput.value.trim();

    if (!token) { replyBox.textContent = "Missing token."; return; }
    if (!message) { replyBox.textContent = "Type a message first."; return; }

    replyBox.textContent = "…sending…";

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message })
      });

      const txt = await res.text();
      // try to pretty-print JSON, otherwise show as-is
      try {
        const json = JSON.parse(txt);
        replyBox.textContent = JSON.stringify(json, null, 2);
      } catch {
        replyBox.textContent = txt;
      }
    } catch (err) {
      replyBox.textContent = "Network error: " + (err?.message || err);
    }
  });
})();
