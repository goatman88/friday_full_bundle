export async function startMic() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return stream; // you can wire to WebRTC/realtime later
}

export async function startCamera(videoEl) {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  videoEl.srcObject = stream;
  await videoEl.play();
  return stream;
}

export function snapCanvas(videoEl, canvasEl) {
  const ctx = canvasEl.getContext('2d');
  canvasEl.width = videoEl.videoWidth;
  canvasEl.height = videoEl.videoHeight;
  ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
  return canvasEl.toDataURL('image/png');
}
