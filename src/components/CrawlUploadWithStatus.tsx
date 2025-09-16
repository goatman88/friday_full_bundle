import React, { useEffect, useRef, useState } from "react";
import API_BASE from "../lib/apiBase";
import { useSSEJob, JobUpdate } from "../hooks/useSSEJob";

type Job = { status: string; progress: number; message?: string };

export default function CrawlUploadWithStatus() {
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string>("");

  const pollTimer = useRef<number | null>(null);
  const { start, stop, supported } = useSSEJob(jobId, (u: JobUpdate) => {
    if (u.ok && u.job) {
      setJob({ status: u.job.status, progress: u.job.progress, message: u.job.message });
      if (u.job.status === "done" || u.job.status === "error") {
        stop();
      }
    }
  });

  // Start SSE or polling when we have a jobId
  useEffect(() => {
    if (!jobId) return;

    if (supported) {
      start();
      return () => stop();
    }

    // fallback: polling
    const poll = async () => {
      const r = await fetch(`${API_BASE}/api/rag/status/${jobId}`).then(x => x.json()).catch(() => null);
      if (r?.ok) {
        setJob(r.job);
        if (r.job.status === "done" || r.job.status === "error") {
          if (pollTimer.current) window.clearInterval(pollTimer.current);
          pollTimer.current = null;
        }
      }
    };
    poll();
    pollTimer.current = window.setInterval(poll, 1200) as any;
    return () => { if (pollTimer.current) window.clearInterval(pollTimer.current); };
  }, [jobId, start, stop, supported]);

  async function run() {
    if (!file) return setMsg("Pick a file first.");
    const content_type = file.type || "application/octet-stream";

    setMsg("Presigning…");
    const ask = await fetch(`${API_BASE}/api/rag/upload_url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_type })
    }).then(r => r.json());

    if (!ask.ok) return setMsg("Presign failed: " + (ask.error || "unknown"));

    setMsg("Uploading…");
    const put = await fetch(ask.url, {
      method: "PUT",
      headers: { "Content-Type": content_type },
      body: file
    });
    if (!put.ok) return setMsg("S3 PUT failed: " + put.status);

    const external_id = crypto.randomUUID();
    setMsg("Confirming (job started)…");
    const confirm = await fetch(`${API_BASE}/api/rag/confirm_upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_uri: ask.s3_uri, title: file.name, external_id })
    }).then(r => r.json());

    if (!confirm.ok) return setMsg("Confirm failed: " + (confirm.error || "unknown"));

    setJobId(confirm.job_id);
    setMsg("Processing on server…");
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Crawl Upload + Live Status (SSE)</h3>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button onClick={run} style={{ marginLeft: 8 }}>Upload</button>

      <div style={{ marginTop: 8 }}>{msg}</div>
      {job && (
        <div style={{ marginTop: 8, fontSize: 14 }}>
          <div>Status: <b>{job.status}</b></div>
          <div>Progress: {job.progress}%</div>
          {job.message && <div>Note: {job.message}</div>}
        </div>
      )}
      {!API_BASE && <div style={{ color: "#b91c1c" }}>Set API base env first.</div>}
    </div>
  );
}



