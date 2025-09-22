export async function getMicStream() {
  return navigator.mediaDevices.getUserMedia({ audio: true })
}

export function recordMicToChunks(stream, onChunk) {
  const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
  rec.ondataavailable = (e) => { if (e.data && e.data.size) onChunk(e.data) }
  rec.start(250) // 4 chunks/sec
  return () => rec.stop()
}
