// src/App.jsx
import React, { useEffect, useRef, useState } from "react";

const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || "";

export default function App() {
  // ---------- state ----------
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [answer, setAnswer] = useState("");
  const [wakeWordArmed, setWakeWordArmed] = useState(true);
  const [voice, setVoice] = useState("alloy");
  const [speed, setSpeed] = useState(1.0);

  const [images, setImages] = useState([]);
  const [visionText, setVisionText] = useState("");

  // media/stream refs
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const silenceMsRef = useRef(0);
  const audioElRef = useRef(null); // for TTS playback
  const mediaSourceRef = useRef(null);
  const sourceBufferRef = useRef(null);
  const abortCurrentTTS = useRef(() => {});

  // VAD settings
  const silenceThreshold = 0.01;
  const maxSilenceMs = 1100;

  function api(p) { return `${BACKEND_BASE}${p}` }

  // ---------- barge-in: stop any playing audio ----------
  function stopTTS() {
    try { abortCurrentTTS.current?.(); } catch {}
    const el = audioElRef.current;
    if (el) {
      el.pause();
      el.removeAttribute("src");
      el.load();
    }
  }

  // ---------- voice capture ----------
  async function startListening() {
    if (recording) return;
    stopTTS(); // barge-in
    setRecording(true);
    setTranscript(""); setAnswer("");

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: "audio/webm" });
    chunksRef.current = [];

    // VAD
    audioCtxRef.current = new AudioContext();
    const src = audioCtxRef.current.createMediaStreamSource(stream);
    analyserRef.current = audioCtxRef.current.createAnalyser();
    analyserRef.current.fftSize = 2048;
    src.connect(analyserRef.current);

    const pcm = new Float32Array(analyserRef.current.fftSize);
    let last = performance.now();
    const tick = () => {
      if (!recording) return;
      analyserRef.current.getFloatTimeDomainData(pcm);
      let sum = 0; for (let i=0;i<pcm.length;i++) sum += pcm[i]*pcm[i];
      const rms = Math.sqrt(sum/pcm.length);
      const now = performance.now(); const dt = now - last; last = now;
      if (rms < silenceThreshold) {
        silenceMsRef.current += dt;
        if (silenceMsRef.current >= maxSilenceMs) return stopListening();
      } else { silenceMsRef.current = 0; }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);

    mediaRecorderRef.current.ondataavailable = (e) => {
      if (e.data && e.data.size) chunksRef.current.push(e.data);
    };
    mediaRecorderRef.current.onstop = () => handleCompleteRecording();

    mediaRecorderRef.current.start(250);
  }

  function stopListening() {
    if (!recording) return;
    setRecording(false);
    silenceMsRef.current = 0;
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current?.stream.getTracks().forEach(t => t.stop());
    audioCtxRef.current?.close();
    analyserRef.current = null; audioCtxRef.current = null;
  }

  async function handleCompleteRecording() {
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    chunksRef.current = [];

    // STT
    const fd = new FormData(); fd.append("file", blob, "input.webm");
    const stt = await (await fetch(api("/api/stt"), { method:"POST", body:fd })).json();
    const heard = (stt.text || "").trim();
    setTranscript(heard);

    let prompt = heard;
    if (wakeWordArmed && /(^|\s)hey\s+friday\b/i.test(heard)) {
      prompt = heard.replace(/(^|\s)hey\s+friday\b/i,"").trim();
    }
    if (!prompt) return;

    // Ask
    const askFd = new FormData(); askFd.append("prompt", prompt);
    const ans = await (await fetch(api("/api/ask"), { method:"POST", body: askFd })).json();
    const text = (ans.text || "").trim(); setAnswer(text);

    // Streaming TTS (fallback to non-stream)
    try {
      await playTTSStream(text, voice, speed);
    } catch {
      await playTTSBlob(text, voice, speed);
    }
  }

  // ---------- TTS helpers ----------
  async function playTTSBlob(text, voice, speed) {
    const fd = new FormData();
    fd.append("text", text); fd.append("voice", voice); fd.append("speed", String(speed));
    const res = await fetch(api("/api/tts"), { method:"POST", body:fd });
    const blob = await res.blob();
    const el = audioElRef.current || (audioElRef.current = new Audio());
    el.src = URL.createObjectURL(blob);
    await el.play();
  }

  async function playTTSStream(text, voice, speed) {
    // Prepare MediaSource
    const el = audioElRef.current || (audioElRef.current = new Audio());
    stopTTS();
    mediaSourceRef.current = new MediaSource();
    const url = URL.createObjectURL(mediaSourceRef.current);
    el.src = url;

    let cancel = false;
    abortCurrentTTS.current = () => { cancel = true; };

    mediaSourceRef.current.addEventListener("sourceopen", async () => {
      try {
        sourceBufferRef.current = mediaSourceRef.current.addSourceBuffer("audio/mpeg");
        const fd = new FormData();
        fd.append("text", text); fd.append("voice", voice); fd.append("speed", String(speed));
        const res = await fetch(api("/api/tts/stream"), { method:"POST", body:fd });
        if (!res.ok) throw new Error("stream http error");

        const reader = res.body.getReader();
        async function pump() {
          if (cancel) return mediaSourceRef.current.endOfStream();
          const { done, value } = await reader.read();
          if (done) { mediaSourceRef.current.endOfStream(); return; }
          await new Promise((resolve, reject) => {
            sourceBufferRef.current.addEventListener("updateend", resolve, { once: true });
            try { sourceBufferRef.current.appendBuffer(value); }
            catch (e) { reject(e); }
          });
          await pump();
        }
        await el.play();
        await pump();
      } catch (e) {
        try { mediaSourceRef.current.endOfStream(); } catch {}
        throw e;
      }
    });
  }

  // ---------- Vision ----------
  function onPickImages(e) {
    const files = Array.from(e.target.files || []);
    setImages(files.map(f => ({ file: f, preview: URL.createObjectURL(f) })));
    setVisionText("");
  }

  async function runVision() {
    if (!images.length) return;
    const fd = new FormData();
    images.forEach((it) => fd.append("files", it.file));
    fd.append(
      "prompt",
      "You are Friday. For all images: give a 2-sentence overview, then 3 bullet observations. Be specific."
    );
    const res = await fetch(api("/api/vision"), { method:"POST", body: fd });
    const js = await res.json();
    setVisionText(js.description || "(no description)");
  }

  return (
    <div style={{ fontFamily:"system-ui, sans-serif", padding:24, maxWidth:900 }}>
      <h1>Friday — Max Voice & Vision</h1>

      <section style={{marginBottom:28}}>
        <h2>🎤 Voice</h2>
        <div style={{display:"flex", gap:12, flexWrap:"wrap", alignItems:"center"}}>
          <button onClick={recording?stopListening:startListening} style={{padding:"10px 16px"}}>
            {recording ? "■ Stop" : "▶︎ Push-to-talk"}
          </button>
          <label>Voice:&nbsp;
            <select value={voice} onChange={e=>setVoice(e.target.value)}>
              <option>alloy</option><option>verse</option><option>breeze</option><option>amber</option>
            </select>
          </label>
          <label>Speed:&nbsp;
            <input type="number" step="0.1" min="0.5" max="1.5" value={speed}
                   onChange={e=>setSpeed(Number(e.target.value))} style={{width:70}}/>
          </label>
          <label style={{display:"flex",alignItems:"center",gap:6}}>
            <input type="checkbox" checked={wakeWordArmed} onChange={e=>setWakeWordArmed(e.target.checked)}/>
            Enable “Hey Friday”
          </label>
        </div>
        <div style={{marginTop:12, fontSize:14, lineHeight:1.5}}>
          <div><b>Heard:</b> {transcript || <i>…</i>}</div>
          <div><b>Friday:</b> {answer || <i>…</i>}</div>
        </div>
      </section>

      <section>
        <h2>👀 Vision (multi-image)</h2>
        <div style={{display:"flex", gap:12, alignItems:"center"}}>
          <input type="file" accept="image/*" multiple onChange={onPickImages}/>
          <button onClick={runVision} disabled={!images.length}>Describe</button>
        </div>
        {!!images.length && (
          <div style={{display:"flex", gap:12, marginTop:12, flexWrap:"wrap"}}>
            {images.map((it, i)=>(
              <img key={i} src={it.preview} alt={"img"+i} style={{width:180, borderRadius:8}}/>
            ))}
          </div>
        )}
        {visionText && (
          <pre style={{whiteSpace:"pre-wrap", marginTop:12}}>{visionText}</pre>
        )}
      </section>
    </div>
  );
}






