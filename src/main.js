// Small helpers
const $ = (sel) => document.querySelector(sel);
const log = (el, ...args) => { el.textContent += args.join(' ') + '\n'; el.scrollTop = el.scrollHeight; };

// DOM
const statusLabel = $('#statusLabel');
const healthBox = $('#healthBox');
const apiHealthBox = $('#apiHealthBox');
const askInput = $('#askInput');
const askBtn = $('#askBtn');
const answerBox = $('#answerBox');

const videoEl = $('#videoEl');
const canvasEl = $('#canvasEl');
const startCamBtn = $('#startCamBtn');
const snapBtn = $('#snapBtn');
const stopCamBtn = $('#stopCamBtn');

const rtProxyLog = $('#rtProxyLog');
const rtProxyConnectBtn = $('#rtProxyConnectBtn');
const rtProxyDisconnectBtn = $('#rtProxyDisconnectBtn');
const rtProxySend = $('#rtProxySend');
const rtProxySendBtn = $('#rtProxySendBtn');

const rtDirectLog = $('#rtDirectLog');
const rtDirectConnectBtn = $('#rtDirectConnectBtn');
const rtDirectDisconnectBtn = $('#rtDirectDisconnectBtn');
// helper
const $ = (id) => document.getElementById(id);
const BACKEND_BASE = (window.BACKEND_BASE || "http://localhost:8000");
let CURRENT_SESSION_ID = null;

async function ensureSession() {
  if (CURRENT_SESSION_ID) return CURRENT_SESSION_ID;
  const res = await fetch(`${BACKEND_BASE}/session`);
  const j = await res.json();
  CURRENT_SESSION_ID = j.session_id;
  $("sessionId").textContent = CURRENT_SESSION_ID;
  // prepare download links
  $("downloadLogJson").href = `${BACKEND_BASE}/session/${CURRENT_SESSION_ID}/log?download=1`;
  $("downloadLogTxt").href  = `${BACKEND_BASE}/session/${CURRENT_SESSION_ID}/log.txt`;
  return CURRENT_SESSION_ID;
}

// Health buttons (if present)
$("pingHealth")?.addEventListener("click", async () => {
  const r = await fetch(`${BACKEND_BASE}/health`);
  $("healthStatus").textContent = r.ok ? "ok" : "error";
  $("healthStatus").className = r.ok ? "ok" : "bad";
});
$("pingApiHealth")?.addEventListener("click", async () => {
  const r = await fetch(`${BACKEND_BASE}/api/health`);
  $("apiHealthStatus").textContent = r.ok ? "ok" : "error";
  $("apiHealthStatus").className = r.ok ? "ok" : "bad";
});

// Session controls
$("newSessionBtn")?.addEventListener("click", async () => {
  CURRENT_SESSION_ID = null;
  await ensureSession();
});
$("resetSessionBtn")?.addEventListener("click", async () => {
  const sid = await ensureSession();
  await fetch(`${BACKEND_BASE}/session/${sid}/reset`, { method: "POST" });
});

// Ask
$("askBtn")?.addEventListener("click", async () => {
  const q = $("askInput").value.trim();
  if (!q) return;
  const sid = await ensureSession();
  const latency = $("latency")?.value || "";
  const r = await fetch(`${BACKEND_BASE}/api/ask`, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify({ q, session_id: sid, latency })
  });
  const j = await r.json();
  $("askOut").textContent = j.answer ? j.answer : JSON.stringify(j, null, 2);
});

// Live SSE transcript
$("startSseBtn")?.addEventListener("click", async () => {
  const sid = await ensureSession();
  const es = new EventSource(`${BACKEND_BASE}/session/${sid}/log/stream`);
  const box = $("sseBox");
  box.textContent += "[stream opened]\n";
  es.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data);
      box.textContent += `[${j.kind}] ${j.text}\n`;
    } catch {
      box.textContent += e.data + "\n";
    }
    box.scrollTop = box.scrollHeight;
  };
  es.addEventListener("final", (e) => {
    try {
      const j = JSON.parse(e.data);
      box.textContent += `[FINAL] ${j.text}\n`;
      box.scrollTop = box.scrollHeight;
    } catch {}
  });
  es.onerror = () => {
    box.textContent += "[stream error]\n";
    es.close();
  };
});

// Clear transcript
$("clearLogBtn")?.addEventListener("click", async () => {
  const sid = await ensureSession();
  await fetch(`${BACKEND_BASE}/session/${sid}/log`, { method: "DELETE" });
  $("sseBox").textContent = "";
});

// Metrics SSE
$("startMetricsBtn")?.addEventListener("click", async () => {
  const es = new EventSource(`${BACKEND_BASE}/metrics/stream`);
  const box = $("metricsBox");
  box.textContent += "[metrics stream opened]\n";
  es.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data);
      box.textContent += JSON.stringify(j) + "\n";
      box.scrollTop = box.scrollHeight;
    } catch {
      box.textContent += e.data + "\n";
    }
  };
  es.onerror = () => {
    box.textContent += "[metrics stream error]\n";
    es.close();
  };
});

// Auto-create a session on page load
ensureSession().catch(console.error);

// ────────────────────────────────────────────────────────────
// Health checks
async function fetchText(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return await r.text();
}
async function runHealth() {
  try {
    const h1 = await fetchText('/health').catch(() => '{"status":"error"}');
    const h2 = await fetchText('/api/health').catch(() => '{"status":"error"}');
    healthBox.textContent = h1;
    apiHealthBox.textContent = h2;
    const ok = h1.includes('"ok"') && h2.includes('"ok"');
    statusLabel.textContent = ok ? 'OK' : 'ERROR';
  } catch (e) {
    statusLabel.textContent = 'ERROR';
  }
}
runHealth();

// ────────────────────────────────────────────────────────────
askBtn.addEventListener('click', async () => {
  const q = askInput.value.trim();
  if (!q) return;
  answerBox.textContent = '…';
  try {
    const r = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ question: q })
    });
    const data = await r.json().catch(() => ({}));
    answerBox.textContent = (data && (data.answer || data.message)) || JSON.stringify(data);
  } catch (e) {
    answerBox.textContent = 'Error: ' + e.message;
  }
});

// ────────────────────────────────────────────────────────────
// Camera + canvas
let mediaStream = null;

startCamBtn.addEventListener('click', async () => {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    videoEl.srcObject = mediaStream;
  } catch (e) {
    alert('Camera error: ' + e.message);
  }
});

snapBtn.addEventListener('click', () => {
  if (!videoEl.srcObject) return;
  const ctx = canvasEl.getContext('2d');
  const { videoWidth: w, videoHeight: h } = videoEl;
  canvasEl.width = w;
  canvasEl.height = h;
  ctx.drawImage(videoEl, 0, 0, w, h);
});

stopCamBtn.addEventListener('click', () => {
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop());
    mediaStream = null;
    videoEl.srcObject = null;
  }
});

// ────────────────────────────────────────────────────────────
// Realtime via backend WS proxy
let proxyWS = null;

rtProxyConnectBtn.addEventListener('click', () => {
  if (proxyWS && proxyWS.readyState === WebSocket.OPEN) return;
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/realtime';
  proxyWS = new WebSocket(wsUrl);
  proxyWS.onopen = () => log(rtProxyLog, '[proxy] connected');
  proxyWS.onmessage = (ev) => log(rtProxyLog, '[proxy] ←', ev.data);
  proxyWS.onerror = (ev) => log(rtProxyLog, '[proxy] error', ev.message || '');
  proxyWS.onclose = () => log(rtProxyLog, '[proxy] closed');
});

rtProxyDisconnectBtn.addEventListener('click', () => {
  if (proxyWS) proxyWS.close();
});

rtProxySendBtn.addEventListener('click', () => {
  if (!proxyWS || proxyWS.readyState !== WebSocket.OPEN) return;
  const msg = rtProxySend.value || '(hello)';
  // You can define your server bridge to accept a simple JSON envelope
  proxyWS.send(JSON.stringify({ type: 'message', data: msg }));
  log(rtProxyLog, '[proxy] →', msg);
});

// ────────────────────────────────────────────────────────────
// Realtime DIRECT (WebRTC using ephemeral key)
let pc = null;      // RTCPeerConnection
let micStream = null;

async function getEphemeralKey() {
  // Your FastAPI route should return: { client_secret: { value: "<ephemeral>" } }
  const r = await fetch('/session');
  if (!r.ok) throw new Error('/session failed: ' + r.status);
  return r.json();
}

async function startDirectRealtime() {
  if (pc) return;

  // 1) Media tracks (mic is strongly recommended for Realtime voice)
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

  // 2) Peer connection
  pc = new RTCPeerConnection();
  micStream.getTracks().forEach(t => pc.addTrack(t, micStream));

  // Optional: handle remote audio
  const remoteAudio = new Audio();
  remoteAudio.autoplay = true;
  pc.ontrack = (e) => {
    if (e.streams && e.streams[0]) {
      remoteAudio.srcObject = e.streams[0];
    }
  };

  pc.onconnectionstatechange = () => {
    log(rtDirectLog, '[direct] state:', pc.connectionState);
  };

  // 3) Create local SDP offer
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  // 4) Fetch ephemeral key from backend, then call OpenAI Realtime (WebRTC)
  const { client_secret } = await getEphemeralKey();
  const EPHEMERAL = client_secret?.value;
  if (!EPHEMERAL) throw new Error('No ephemeral key from /session');

  // 5) POST the offer SDP to OpenAI. Replace with your desired realtime model.
  const model = 'gpt-4o-realtime-preview-2024-12-17';
  const openaiURL = `https://api.openai.com/v1/realtime?model=${encodeURIComponent(model)}`;
  const resp = await fetch(openaiURL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${EPHEMERAL}`,
      'Content-Type': 'application/sdp'
    },
    body: offer.sdp
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error('OpenAI Realtime SDP failed: ' + resp.status + ' ' + txt);
  }

  const answerSDP = await resp.text();
  await pc.setRemoteDescription({ type: 'answer', sdp: answerSDP });
  log(rtDirectLog, '[direct] connected (WebRTC)');

  // You can add DataChannel for text messages:
  const dc = pc.createDataChannel('oai-data');
  dc.onopen = () => log(rtDirectLog, '[direct] datachannel open');
  dc.onmessage = (e) => log(rtDirectLog, '[direct] ←', e.data);
}

async function stopDirectRealtime() {
  if (pc) {
    pc.getSenders().forEach(s => { try { s.track && s.track.stop(); } catch {} });
    pc.close();
    pc = null;
  }
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  log(rtDirectLog, '[direct] disconnected');
}

rtDirectConnectBtn.addEventListener('click', () => {
  startDirectRealtime().catch(e => log(rtDirectLog, 'error:', e.message));
});
rtDirectDisconnectBtn.addEventListener('click', stopDirectRealtime);


