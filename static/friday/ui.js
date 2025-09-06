(function () {
  const $ = (s) => document.querySelector(s);

  const tokenInput = $("#token");
  const saveBtn    = $("#saveToken");
  const sendBtn    = $("#send");
  const clearBtn   = $("#clear");
  const copyBtn    = $("#copy");
  const msgInput   = $("#msg");
  const replyBox   = $("#reply");

  // load dev token
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
    if (!token)  { replyBox.textContent = "Missing token.";  return; }
    if (!message){ replyBox.textContent = "Type a message."; return; }

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
      const text = await res.text();
      try { replyBox.textContent = JSON.stringify(JSON.parse(text), null, 2); }
      catch { replyBox.textContent = text; }
    } catch (e) {
      replyBox.textContent = "Network error: " + (e?.message || e);
    }
  });
})();
