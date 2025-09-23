// frontend/src/main.js
const $ = (id) => document.getElementById(id);

const BACKEND_BASE =
  import.meta.env.VITE_BACKEND_BASE?.replace(/\/$/, "") ||
  (location.origin.includes(":5173") ? "http://localhost:8000" : location.origin);

// --- HEALTH ---
async function probe() {
  const h = await fetch(`${BACKEND_BASE}/health`).then(r => r.json()).catch(() => ({status:"ERROR"}));
  const ah = await fetch(`${BACKEND_BASE}/api/health`).then(r => r.json()).catch(() => ({status:"ERROR"}));
  $("healthBox").textContent = JSON.stringify(h, null, 2);
  $("apiHealthBox").textContent = JSON.stringify(ah, null, 2);
  $("status").textContent = (h.status === "ok" && ah.status === "ok") ? "OK" : "ERROR";
}
probe();

// --- ASK FORM ---
$("askBtn").onclick = async () => {
  const q = $("q").value.trim();
  const latency = $("latencySel").value;
  $("answer").textContent = "Thinking…";
  try {
    const r = await fetch(`${BACKEND_BASE}/api/ask`, {
      method: "POST",
      headers: {"content-type":"application/json"},
      body: JSON.stringify({ q, latency })
    });
    const data = await r.json();
    $("answer").textContent = data.answer || JSON.stringify(data, null, 2);
  } catch (e) {
    $("answer").textContent = String(e);
  }
};

// --- CAMERA + SNAP ---
let mediaStream = null;
$("startCamBtn").onclick = async () => {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    $("cam").srcObject = mediaStream;
  } catch (e) {
    logRT("camera error: " + e.message);
  }
};
$("snapBtn").onclick = () => {
  if (!mediaStream) return;
  const v = $("cam");
  const c = $("snapCanvas");
  const ctx = c.getContext("2d");
  ctx.drawImage(v, 0, 0, c.width, c.height);
};

// --- REALTIME ---
const logRT = (msg) => {
  const box = $("rtLog");
  box.textContent += msg + "\n";
  box.scrollTop = box.scrollHeight;
};

// SDP helper
async function createAndPostOffer(toUrl) {
  const pc = new RTCPeerConnection();
  // Microphone
  try {
    const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
    mic.getTracks().forEach(t => pc.addTrack(t, mic));
  } catch (e) {
    logRT("mic error: " + e.message);
  }

  // (optional) camera into PC (not required by Realtime, but some demos use it)
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => pc.addTrack(t, mediaStream));
  }

  const audioEl = $("rtAudio");
  pc.ontrack = (evt) => {
    const [stream] = evt.streams;
    audioEl.srcObject = stream;
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const r = await fetch(toUrl, {
    method: "POST",
    headers: {"content-type":"application/sdp"},
    body: offer.sdp
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error("SDP proxy failed: " + t);
  }
  const answer = await r.text();
  const desc = { type: "answer", sdp: answer };
  await pc.setRemoteDescription(desc);
  return pc; // keep the connection alive
}

$("rtServerBtn").onclick = async () => {
  const latency = $("rtLatencySel").value;
  const url = `${BACKEND_BASE}/realtime/sdp${latency ? `?latency=${latency}` : ""}`;
  try {
    logRT("Starting Realtime via server…");
    await createAndPostOffer(url);
    logRT("Realtime connected (server).");
  } catch (e) {
    logRT("Realtime error: " + e.message);
  }
};

$("rtDirectBtn").onclick = async () => {
  const latency = $("rtLatencySel").value;
  const model = latency === "ultra"
    ? "gpt-4o-realtime-preview-lite"
    : (latency === "balanced" ? "gpt-4o-realtime-preview" : "gpt-4o-realtime-preview-2024-12-17");

  try {
    logRT("Starting Realtime direct…");
    const url = `https://api.openai.com/v1/realtime?model=${encodeURIComponent(model)}&voice=${encodeURIComponent("verse")}`;
    // The direct path needs a server-issued ephemeral token in real apps.
    // For local demos ONLY you can use a permanent key; we DO NOT do that here.
    logRT("Direct mode requires ephemeral or server token. Use server button in prod.");
  } catch (e) {
    logRT("Realtime direct error: " + e.message);
  }
};

