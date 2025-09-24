const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function checkHealth() {
  const root = await fetch(`${apiBase}/health`).then(r => r.json());
  document.getElementById("rootHealth").textContent = JSON.stringify(root);

  const api = await fetch(`${apiBase}/api/health`).then(r => r.json());
  document.getElementById("apiHealth").textContent = JSON.stringify(api);
}

async function askQuestion() {
  const q = document.getElementById("askInput").value;
  const res = await fetch(`${apiBase}/api/ask`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({prompt: q})
  }).then(r => r.json());
  document.getElementById("askAnswer").textContent = JSON.stringify(res);
}

// Camera & mic hooks
async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  document.getElementById("video").srcObject = stream;
}

async function startMic() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  console.log("Mic started:", stream);
}

window.onload = checkHealth;
window.askQuestion = askQuestion;
window.startCamera = startCamera;
window.startMic = startMic;



