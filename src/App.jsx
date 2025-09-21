// src/App.jsx
import React, { useEffect, useRef, useState } from "react";

const BACKEND_BASE =
  import.meta.env.VITE_BACKEND_URL || ""; // leave empty when frontend is proxied to same origin

export default function App() {
  // ---------------- State ----------------
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [answer, setAnswer] = useState("");
  const [wakeWordArmed, setWakeWordArmed] = useState(true);
  const [voice, setVoice] = useState("alloy");
  const [speed, setSpeed] = useState(1.0);
  const [imagePreview, setImagePreview] = useState(null);
  const [visionResult, setVisionResult] = useState("");

  // Media stuff
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const silenceMsRef = useRef(0);
  const silenceThreshold = 0.01; // 0→1 amplitude
  const maxSilenceMs = 1200;     // stop after ~1.2s of silence

  // ------------- Helpers -----------------
  function api(path) {
    return `${BACKEND_BASE}${path}`;
  }

  async function playMp3Blob(blob) {
    const audio = new Audio(URL.createObjectURL(blob));
    await audio.play();
  }

  // ----------- Recording/VAD -------------
  async function startListening() {
    if (recording) return;
    setRecording(true);
    setTranscript("");
    setAnswer("");

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: "audio/webm" });
    chunksRef.current = [];

    // WebAudio graph for live silence detection
    audioCtxRef.current = new AudioContext();
    const src = audioCtxRef.current.createMediaStreamSource(stream);
    analyserRef.current = audioCtxRef.current.createAnalyser();
    analyserRef.current.fftSize = 2048;
    src.connect(analyserRef.current);

    let lastTick = performance.now();
    const pcm = new Float32Array(analyserRef.current.fftSize);

    function tick() {
      if (!recording) return;
      analyserRef.current.getFloatTimeDomainData(pcm);
      // Root-mean-square energy
      let sum = 0;
      for (let i = 0; i < pcm.length; i++) sum += pcm[i] * pcm[i];
      const rms = Math.sqrt(sum / pcm.length);

      const now = performance.now();
      const delta = now - lastTick;
      lastTick = now;

      if (rms < silenceThreshold) {
        silenceMsRef.current += delta;
        if (silenceMsRef.current >= maxSilenceMs) {
          stopListening(); // auto-stop on silence
          return;
        }
      } else {
        silenceMsRef.current = 0;
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);

    mediaRecorderRef.current.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    };
    mediaRecorderRef.current.onstop = () => handleRecordingComplete();

    mediaRecorderRef.current.start(250); // gather chunks every 250ms
  }

  function stopListening() {
    if (!recording) return;
    setRecording(false);
    silenceMsRef.current = 0;
    mediaRecorderRef.current?.stop();
    // Close inputs
    mediaRecorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    mediaRecorderRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    analyserRef.current = null;
  }

  async function handleRecordingComplete() {
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    chunksRef.current = [];

    // --- STT ---
    const fd = new FormData();
    fd.append("file", blob, "input.webm");
    const sttRes = await fetch(api("/api/stt"), { method: "POST", body: fd });
    const sttJson = await sttRes.json();
    const heard = (sttJson.text || "").trim();
    setTranscript(heard);

    // Optional wake word
    const isWake = wakeWordArmed && /(^|\s)hey\s+friday\b/i.test(heard);
    const userPrompt = isWake ? heard.replace(/(^|\s)hey\s+friday\b/i, "").trim() : heard;

    if (!userPrompt) return;

    // --- Ask LLM ---
    const askFd = new FormData();
    askFd.append("prompt", userPrompt);
    const askRes = await fetch(api("/api/ask"), { method: "POST", body: askFd });
    const askJson = await askRes.json();
    const reply = (askJson.text || "").trim();
    setAnswer(reply);

    // --- TTS ---
    const ttsFd = new FormData();
    ttsFd.append("text", reply);
    ttsFd.append("voice", voice);
    ttsFd.append("speed", String(speed));
    const ttsRes = await fetch(api("/api/tts"), { method: "POST", body: ttsFd });
    await playMp3Blob(await ttsRes.blob());
  }

  // --------------- Vision ----------------
  async function handleImageUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    setVisionResult("");

    const fd = new FormData();
    fd.append("file", file);
    fd.append(
      "prompt",
      "You are Friday. Give a 2-sentence overview of the image, then list 3 specific observations. Be concise."
    );

    const res = await fetch(api("/api/vision"), { method: "POST", body: fd });
    const json = await res.json();
    setVisionResult(json.description || "(no description)");
  }

  // --------------- UI --------------------
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 24, maxWidth: 820 }}>
      <h1>Friday — Voice & Vision</h1>

      <section style={{ marginBottom: 28 }}>
        <h2>🎤 Voice</h2>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button onClick={recording ? stopListening : startListening}
                  style={{ padding: "10px 16px", fontSize: 16 }}>
            {recording ? "■ Stop" : "▶︎ Push-to-talk"}
          </button>

          <label>
            Voice:&nbsp;
            <select value={voice} onChange={(e) => setVoice(e.target.value)}>
              <option>alloy</option>
              <option>verse</option>
              <option>breeze</option>
              <option>amber</option>
            </select>
          </label>

          <label>
            Speed:&nbsp;
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="1.5"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              style={{ width: 70 }}
            />
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="checkbox"
              checked={wakeWordArmed}
              onChange={(e) => setWakeWordArmed(e.target.checked)}
            />
            Enable “Hey Friday” wake-word
          </label>
        </div>

        <div style={{ marginTop: 14, fontSize: 14, lineHeight: 1.5 }}>
          <div><b>Heard:</b> {transcript || <i>(…)</i>}</div>
          <div><b>Friday:</b> {answer || <i>(…)</i>}</div>
        </div>
      </section>

      <section>
        <h2>👀 Vision</h2>
        <input type="file" accept="image/*" onChange={handleImageUpload} />
        {imagePreview && (
          <div style={{ marginTop: 12, display: "flex", gap: 16 }}>
            <img src={imagePreview} alt="preview" style={{ maxWidth: 280, borderRadius: 8 }} />
            <div style={{ whiteSpace: "pre-wrap" }}>{visionResult}</div>
          </div>
        )}
      </section>
    </div>
  );
}





