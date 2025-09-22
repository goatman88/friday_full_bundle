export async function startCamera(videoEl) {
  const s = await navigator.mediaDevices.getUserMedia({ video: true })
  videoEl.srcObject = s
  await videoEl.play()
  return s
}
export function snapToCanvas(videoEl, canvasEl) {
  const w = videoEl.videoWidth, h = videoEl.videoHeight
  canvasEl.width = w; canvasEl.height = h
  const ctx = canvasEl.getContext('2d')
  ctx.drawImage(videoEl, 0, 0, w, h)
  return canvasEl.toDataURL('image/png')
}
