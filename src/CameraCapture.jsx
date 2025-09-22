// src/CameraCapture.jsx
import React, { useEffect, useRef, useState } from 'react';

export default function CameraCapture({ onSnap }) {
  const vidRef = useRef(null);
  const canvasRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stream;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        vidRef.current.srcObject = stream;
        await vidRef.current.play();
        setReady(true);
      } catch (e) { console.error(e); }
    })();
    return () => stream && stream.getTracks().forEach(t => t.stop());
  }, []);

  const snap = () => {
    const v = vidRef.current, c = canvasRef.current;
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    c.toBlob((blob) => onSnap && onSnap(blob), 'image/jpeg', 0.9);
  };

  return (
    <div style={{ display:'grid', gap:8 }}>
      <video ref={vidRef} style={{ width:'100%', maxWidth:420, border:'1px solid #444' }} muted playsInline />
      <button onClick={snap} disabled={!ready}>Snap</button>
      <canvas ref={canvasRef} style={{ display:'none' }} />
    </div>
  );
}
