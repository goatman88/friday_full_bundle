// frontend/src/main.js
//
// One file to run the whole demo in dev and on Render.
// - Health checks (/health and /api/health)
// - Ask form -> POST /api/ask
// - Start/Stop Camera preview
// - Start Realtime (mic + optional camera) via secure SDP proxy at /api/realtime/sdp
//
// API base:
//   Dev:    vite proxy routes /health and /api/* to http://localhost:8000
//   Render: set VITE_API_BASE=https://<your-backend>.onrender.com (or leave relative if same domain)

const API_BASE =
  (import.meta && import.meta.env && import.meta.env.VITE_API_BASE) || ""; // empty means "same origin"

// ---------- tiny helpers ----------
const $ = (id) => document.getElementById(id);
const pre = (el, obj) => (el ? (el.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2)) : null);

async function getJSON(path) {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
async function postJSON(path, body) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ---------- health banners ----------
const preHealthRoot = $("pre-health-root");
const preHealthApi = $("pre-health-api");
const statusEl = $("status-label");

(async () => {
  try {
    const a = await getJSON("/health");
    const b = await getJSON("/api/health");
    pre(preHealthRoot, a);
    pre(preHealthApi, b);
    if (statusEl) statusEl.textContent = "OK";
  } catch (err) {
    pre(preHealthRoot, `ERROR: ${err}`);
    pre(preHealthApi, `ERROR: ${err}`);
    if (statusEl) statusEl.textContent = "ERROR";
  }
})();

// ---------- ask form ----------
const askForm = $("ask-form");
const askInput = $("ask-input");
const answerPre = $("answer-pre");

if (askForm) {
  askForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (askInput?.value || "").trim();
    if (!q) return;
    pre(answerPre, "…thinking…");
    try {
      const { answer } = await postJSON("/api/ask", { q });
      pre(answerPre, answer || "(empty)");
    } catch (err) {
      pre(answerPre, `Error: ${err}`);
    }
  });
}

// ---------- camera controls ----------
let localStream = null;
const localVideo = $("localVideo");

async function startCamera() {
  if (localStream) return;
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  if (localVideo) localVideo.srcObject = localStream;
}

function stopCamera() {
  if (!localStream) return;
  localStream.getTracks().forEach((t) => t.stop());
  localStream = null;
  if (localVideo) localVideo.srcObject = null;
}

$("btnStartCam")?.addEventListener("click", startCamera);
$("btnStopCam")?.addEventListener("click", stopCamera);

// ---------- OpenAI Realtime via secure SDP proxy ----------
const remoteAudio = $("remoteAudio");

async function startRealtime() {
  // Peer connection
  const pc = new RTCPeerConnection();

  // local media (mic always, video if you've started camera or want fresh getUserMedia)
  let micStream;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  } catch (err) {
    alert("Microphone permission is required for Realtime.");
    throw err;
  }
  micStream.getTracks().forEach((t) => pc.addTrack(t, micStream));

  if (localStream) {
    localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
  }

  pc.ontrack = (evt) => {
    if (evt.streams && evt.streams[0] && remoteAudio) {
      remoteAudio.srcObject = evt.streams[0];
    }
  };

  // Optional data channel for events
  const dc = pc.createDataChannel("oai-events");
  dc.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      console.debug("oai:", msg);
    } catch {
      console.debug("oai:", e.data);
    }
  };

  const offer = await pc.createOffer({
    offerToReceiveAudio: true,
    offerToReceiveVideo: false,
  });
  await pc.setLocalDescription(offer);

  // use the backend proxy — keep your API key server-side
  const answerSDP = await fetch(`${API_BASE}/api/realtime/sdp`, {
    method: "POST",
    headers: { "Content-Type": "application/sdp" },
    body: offer.sdp,
  }).then((r) => r.text());

  await pc.setRemoteDescription({ type: "answer", sdp: answerSDP });

  // stash for dev
  window._oai_pc = pc;
}

$("btnStartRealtime")?.addEventListener("click", startRealtime);

