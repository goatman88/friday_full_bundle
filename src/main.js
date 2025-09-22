import { sse, wsStream, askOnce, getHistory } from './streaming';
import { startMic, startCamera, snapCanvas } from './capture';

const els = {
  status: document.querySelector('#status'),
  ask: document.querySelector('#ask'),
  send: document.querySelector('#send'),
  out: document.querySelector('#out'),
  cam: document.querySelector('#cam'),
  snap: document.querySelector('#snap'),
  canvas: document.querySelector('#canvas')
};

let cameraStream = null;

// camera
document.querySelector('#startCam').onclick = async () => {
  cameraStream = await startCamera(els.cam);
  els.status.textContent = 'Camera: ON';
};
els.snap.onclick = () => {
  const dataUrl = snapCanvas(els.cam, els.canvas);
  els.snap.dataset.dataurl = dataUrl;
  els.status.textContent = 'Snapshot captured';
};

// SSE
document.querySelector('#sendSSE').onclick = () => {
  const img = els.snap.dataset.dataurl;
  els.out.textContent = '';
  sse(els.ask.value, t => els.out.textContent += t, () => {}, img);
};

// WebSocket
document.querySelector('#sendWS').onclick = () => {
  els.out.textContent = '';
  wsStream(els.ask.value, t => els.out.textContent += t, () => {});
};

// one-shot
els.send.onclick = async () => {
  const img = els.snap.dataset.dataurl;
  const r = await askOnce(els.ask.value, img);
  els.out.textContent = r.answer;
};

// history
document.querySelector('#loadHist').onclick = async () => {
  const hist = await getHistory();
  console.log(hist);
};
