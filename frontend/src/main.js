// frontend/src/main.js
const $ = (id) => document.getElementById(id);
const BACKEND_BASE =
  import.meta.env.VITE_BACKEND_BASE?.replace(/\/$/, "") ||
  (location.origin.includes(":5173") ? "http://localhost:8000" : location.origin);

// ---- HEALTH ----
async function probe() {
  const h = await fetch(`${BACKEND_BASE}/health`).then(r => r.json()).catch(() => ({status:"ERROR"}));
  const ah = await fetch(`${BACKEND_BASE}/api/health`).then(r => r.json()).catch(() => ({status:"ERROR"}));
  $("healthBox").textContent = JSON.stringify(h, null, 2);
  $("apiHealthBox").textContent = JSON.stringify(ah, null, 2);
  $("status").textContent = (h.status === "ok" && ah.status === "ok") ? "OK" : "ERROR";
}
probe();

// ---- ASK ----
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

// ---- CAMERA ----
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

// ---- REALTIME (WebRTC) ----
const logRT = (msg) => {
  const box = $("rtLog");
  box.textContent += msg + "\n";
  box.scrollTop = box.scrollHeight;
};

async function createAndPostOffer(toUrl, bearerProvider) {
  const pc = new RTCPeerConnection();

  // mic
  try {
    const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
    mic.getTracks().forEach(t => pc.addTrack(t, mic));
  } catch (e) {
    logRT("mic error: " + e.message);
  }
  // camera (optional)
  if (mediaStream) mediaStream.getTracks().forEach(t => pc.addTrack(t, mediaStream));

  const audioEl = $("rtAudio");
  pc.ontrack = (evt) => {
    const [stream] = evt.streams;
    audioEl.srcObject = stream;
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  // either hit our server SDP proxy or send directly with an ephemeral token
  if (bearerProvider) {
    const token = await bearerProvider();
    const r = await fetch(toUrl, {
      method: "POST",
      headers: {
        "content-type": "application/sdp",
        "authorization": `Bearer ${token}`
      },
      body: offer.sdp
    });
    if (!r.ok) throw new Error(await r.text());
    const answer = await r.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answer });
  } else {
    const r = await fetch(toUrl, { method:"POST", headers:{ "content-type":"application/sdp" }, body: offer.sdp });
    if (!r.ok) throw new Error(await r.text());
    const answer = await r.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answer });
  }

  return pc;
}

$("rtServerBtn").onclick = async () => {
  const latency = $("rtLatencySel").value;
  const url = `${BACKEND_BASE}/realtime/sdp${latency ? `?latency=${latency}` : ""}`;
  try {
    logRT("Starting Realtime via server…");
    await createAndPostOffer(url, /*bearerProvider*/ null);
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

  // get ephemeral from our backend
  async function getEphemeral() {
    const r = await fetch(`${BACKEND_BASE}/ephemeral`, {
      method: "POST",
      headers: {"content-type":"application/json"},
      body: JSON.stringify({ latency })
    });
    const j = await r.json();
    if (!j.ephemeral_token) throw new Error("no ephemeral token");
    return j.ephemeral_token;
  }

  try {
    logRT("Starting Realtime direct (ephemeral) …");
    const url = `https://api.openai.com/v1/realtime?model=${encodeURIComponent(model)}&voice=${encodeURIComponent("verse")}`;
    await createAndPostOffer(url, getEphemeral);
    logRT("Realtime connected (direct).");
  } catch (e) {
    logRT("Realtime direct error: " + e.message);
  }
};
// Live SSE transcript
$("startSseBtn").onclick = async () => {
  const sid = await ensureSession();
  const base = BACKEND_BASE;
  const es = new EventSource(`${base}/session/${sid}/log/stream`);
  const box = $("sseBox");
  es.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data);
      box.textContent += `[${j.kind}] ${j.text}\n`;
      box.scrollTop = box.scrollHeight;
    } catch {
      box.textContent += e.data + "\n";
    }
  };
  es.onerror = () => {
    box.textContent += "[stream error]\n";
    es.close();
  };
};

// ---- Wake: keyboard fallback (Shift+Space) ----
let hotPressed = false;
window.addEventListener("keydown", (e) => {
  if (e.shiftKey && e.code === "Space" && !hotPressed) {
    hotPressed = true;
    $("rtServerBtn").click(); // start realtime quickly
    setTimeout(() => (hotPressed = false), 800);
  }
});

// ---- Wake: Porcupine helper triggers POST /wake, we long-poll here ----
async function longPollWake() {
  while (true) {
    try {
      const r = await fetch(`${BACKEND_BASE}/wake/next`);
      const j = await r.json();
      if (j.wake) {
        logRT("Wake signal received.");
        $("rtServerBtn").click();
      }
    } catch {}
  }
}
longPollWake();


